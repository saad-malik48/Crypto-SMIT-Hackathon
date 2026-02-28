"""
etl_pipeline.py — ETL Orchestrator
=====================================
Responsibilities:
  • Compose extract → transform → load into one atomic pipeline run
  • Schedule runs every N minutes via APScheduler (or fallback loop)
  • Structured logging with per-run summary stats
  • Graceful shutdown on SIGINT / SIGTERM
  • Expose run_once() for ad-hoc / testing calls

Design choices:
  • APScheduler BackgroundScheduler runs in its own thread
  • run_once() returns PipelineResult so callers can inspect success/failure
  • All exceptions caught at orchestrator level — pipeline never crashes scheduler
  • Consecutive failure counter with circuit-breaker at 5 failures
"""

import logging
import signal
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

# ─── APScheduler (optional) ──────────────────────────────────────────────────
try:
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.interval import IntervalTrigger
    _APScheduler = True
except ImportError:
    _APScheduler = False
    logger.info("APScheduler not installed — using built-in sleep loop")

from config import ETL_INTERVAL_MINUTES
from extract import extract
from transform import transform, summarize
from load import load, LoadResult


# ══════════════════════════════════════════════════════════════════════════════
#  Result dataclass
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class PipelineResult:
    run_at:       datetime = field(default_factory=lambda: datetime.now(tz=timezone.utc))
    success:      bool     = False
    coins_extracted: int   = 0
    coins_transformed: int = 0
    load_result:  Optional[LoadResult] = None
    error:        Optional[str]        = None
    duration_s:   float = 0.0
    summary:      dict  = field(default_factory=dict)

    def __str__(self) -> str:
        status = "✓ OK" if self.success else f"✗ FAILED: {self.error}"
        return (
            f"[{self.run_at.strftime('%H:%M:%S')}] Pipeline {status} | "
            f"extract={self.coins_extracted} transform={self.coins_transformed} "
            f"load={self.load_result} | {self.duration_s:.2f}s"
        )


# ══════════════════════════════════════════════════════════════════════════════
#  Run once
# ══════════════════════════════════════════════════════════════════════════════

def run_once() -> PipelineResult:
    """
    Execute one full ETL cycle: extract → transform → load.

    Returns PipelineResult regardless of success/failure.
    Never raises — exceptions are captured in result.error.
    """
    result = PipelineResult()
    t0 = time.perf_counter()

    logger.info("═" * 60)
    logger.info("ETL PIPELINE START  %s", result.run_at.isoformat())
    logger.info("═" * 60)

    try:
        # ── Extract ───────────────────────────────────────────────────────────
        logger.info("── Stage 1: EXTRACT")
        raw_coins, extracted_at = extract()
        result.coins_extracted = len(raw_coins)
        logger.info("   ✓ Extracted %d coins at %s", len(raw_coins), extracted_at.isoformat())

        # ── Transform ─────────────────────────────────────────────────────────
        logger.info("── Stage 2: TRANSFORM")
        coins = transform(raw_coins, extracted_at)
        result.coins_transformed = len(coins)
        result.summary = summarize(coins)
        logger.info("   ✓ Transformed %d records", len(coins))
        _log_summary(result.summary)

        # ── Load ──────────────────────────────────────────────────────────────
        logger.info("── Stage 3: LOAD")
        load_result = load(coins)
        result.load_result = load_result
        logger.info("   ✓ %s", load_result)

        result.success = True

    except Exception as exc:
        result.error = str(exc)
        logger.error("   ✗ Pipeline error: %s", exc, exc_info=True)

    finally:
        result.duration_s = time.perf_counter() - t0
        logger.info("ETL PIPELINE END    duration=%.2fs  success=%s", result.duration_s, result.success)
        logger.info("═" * 60)

    return result


def _log_summary(s: dict) -> None:
    if not s:
        return
    logger.info(
        "   Summary: mcap=$%s  gainers=%d  losers=%d  "
        "top_gainer=%s(+%.2f%%)  most_volatile=%s",
        f"{s.get('total_market_cap', 0):,.0f}",
        s.get("gainers", 0),
        s.get("losers", 0),
        s.get("top_gainer", {}).get("coin", "?"),
        s.get("top_gainer", {}).get("change", 0),
        s.get("most_volatile", {}).get("coin", "?"),
    )


# ══════════════════════════════════════════════════════════════════════════════
#  Scheduler
# ══════════════════════════════════════════════════════════════════════════════

_consecutive_failures = 0
_CIRCUIT_BREAKER_LIMIT = 5


def _scheduled_job() -> None:
    """Wrapper called by scheduler — manages circuit breaker."""
    global _consecutive_failures
    result = run_once()
    if result.success:
        _consecutive_failures = 0
    else:
        _consecutive_failures += 1
        if _consecutive_failures >= _CIRCUIT_BREAKER_LIMIT:
            logger.critical(
                "Circuit breaker tripped: %d consecutive failures. "
                "Stopping scheduler. Investigate and restart.",
                _consecutive_failures,
            )
            # Stop scheduler from within the job
            _stop_scheduler()


_scheduler: Optional["BackgroundScheduler"] = None

def _stop_scheduler():
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("APScheduler stopped")


def _handle_signal(sig, frame):
    logger.info("Signal %d received — shutting down ETL pipeline", sig)
    _stop_scheduler()
    sys.exit(0)


# ══════════════════════════════════════════════════════════════════════════════
#  Fallback: simple sleep loop (no APScheduler)
# ══════════════════════════════════════════════════════════════════════════════

def _run_loop(interval_minutes: int) -> None:
    """Simple blocking loop as APScheduler alternative."""
    interval_s = interval_minutes * 60
    logger.info("Starting sleep-loop scheduler (interval=%dm)", interval_minutes)
    while True:
        _scheduled_job()
        logger.info("Next run in %d minutes — sleeping...", interval_minutes)
        time.sleep(interval_s)


# ══════════════════════════════════════════════════════════════════════════════
#  Main entry point
# ══════════════════════════════════════════════════════════════════════════════

def start(interval_minutes: int = ETL_INTERVAL_MINUTES, run_immediately: bool = True) -> None:
    """
    Start the ETL scheduler.

    Args:
        interval_minutes: How often to run the pipeline.
        run_immediately:  If True, execute one run before scheduling.
    """
    global _scheduler

    signal.signal(signal.SIGINT,  _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    logger.info(
        "ETL Orchestrator starting | interval=%dm | backend=%s",
        interval_minutes,
        "APScheduler" if _APScheduler else "sleep-loop",
    )

    if run_immediately:
        logger.info("Executing immediate first run...")
        _scheduled_job()

    if _APScheduler:
        _scheduler = BackgroundScheduler(timezone="UTC")
        _scheduler.add_job(
            _scheduled_job,
            trigger=IntervalTrigger(minutes=interval_minutes),
            id="etl_pipeline",
            name="Crypto ETL",
            replace_existing=True,
            misfire_grace_time=60,
        )
        _scheduler.start()
        logger.info(
            "APScheduler running (next run in ~%d min) — press Ctrl+C to stop",
            interval_minutes,
        )
        try:
            while True:
                time.sleep(30)
        except (KeyboardInterrupt, SystemExit):
            _stop_scheduler()
    else:
        # Blocking loop
        _run_loop(interval_minutes)


# ══════════════════════════════════════════════════════════════════════════════
#  CLI
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)s  %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler("logs/etl_pipeline.log", encoding="utf-8"),
        ],
    )

    parser = argparse.ArgumentParser(description="Crypto ETL Pipeline Orchestrator")
    parser.add_argument("--once",     action="store_true", help="Run pipeline once and exit")
    parser.add_argument("--interval", type=int, default=ETL_INTERVAL_MINUTES,
                        help=f"Interval in minutes (default: {ETL_INTERVAL_MINUTES})")
    args = parser.parse_args()

    if args.once:
        result = run_once()
        print(f"\n{result}")
        sys.exit(0 if result.success else 1)
    else:
        start(interval_minutes=args.interval)


# ══════════════════════════════════════════════════════════════════════════════
#  Helper for dashboard initialization
# ══════════════════════════════════════════════════════════════════════════════

def run_etl_once() -> bool:
    """
    Simple wrapper for dashboard to run ETL once and return success status.
    Returns True if successful, False otherwise.
    """
    result = run_once()
    return result.success
