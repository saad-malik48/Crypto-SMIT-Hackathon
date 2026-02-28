"""
extract.py — ETL Extract Layer
================================
Responsibilities:
  • Fetch top-N coins from CoinGecko /coins/markets endpoint
  • Validate response schema (required fields, types)
  • Retry with exponential backoff on transient errors
  • Save raw JSON snapshots to raw_data/ for audit/replay
  • Return a typed list of raw dicts for the transform layer

Design choices:
  • httpx over requests for connection pooling & timeout control
  • Pydantic for response validation (catches API drift early)
  • Raw JSON saved per-run with ISO timestamp filename
  • Structured logging at every decision point
"""

import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ─── Try httpx, fall back to urllib ──────────────────────────────────────────
try:
    import httpx
    _HTTP_BACKEND = "httpx"
except ImportError:
    import urllib.request
    import urllib.error
    _HTTP_BACKEND = "urllib"
    logger.info("httpx not installed — using urllib fallback")

# ─── Try pydantic for validation ─────────────────────────────────────────────
try:
    from pydantic import BaseModel, validator, ValidationError
    _PYDANTIC = True
except ImportError:
    _PYDANTIC = False
    logger.info("pydantic not installed — using dict-based validation")

from config import (
    COINGECKO_BASE, COINGECKO_KEY, TOP_N_COINS, COINS_VS,
    RAW_DIR, REQUEST_TIMEOUT, MAX_RETRIES, RETRY_BACKOFF,
)


# ══════════════════════════════════════════════════════════════════════════════
#  Pydantic Schema (if available)
# ══════════════════════════════════════════════════════════════════════════════

if _PYDANTIC:
    class CoinRaw(BaseModel):
        id:                         str
        symbol:                     str
        name:                       str
        current_price:              Optional[float]
        market_cap:                 Optional[float]
        total_volume:               Optional[float]
        price_change_percentage_24h: Optional[float]
        market_cap_rank:            Optional[int]

        # Coerce None → 0.0 for numeric fields so transform layer never sees None
        @validator("current_price", "market_cap", "total_volume",
                   "price_change_percentage_24h", pre=True, always=True)
        def coerce_float(cls, v):
            return float(v) if v is not None else 0.0

        @validator("market_cap_rank", pre=True, always=True)
        def coerce_int(cls, v):
            return int(v) if v is not None else 9999


REQUIRED_KEYS = {
    "id", "symbol", "name", "current_price",
    "market_cap", "total_volume",
    "price_change_percentage_24h", "market_cap_rank",
}


# ══════════════════════════════════════════════════════════════════════════════
#  HTTP helpers
# ══════════════════════════════════════════════════════════════════════════════

def _build_headers() -> dict:
    headers = {"Accept": "application/json", "User-Agent": "CryptoAnalytics/1.0"}
    if COINGECKO_KEY:
        headers["x-cg-pro-api-key"] = COINGECKO_KEY
    return headers


def _build_url() -> str:
    params = (
        f"vs_currency={COINS_VS}"
        f"&order=market_cap_desc"
        f"&per_page={TOP_N_COINS}"
        f"&page=1"
        f"&sparkline=false"
        f"&price_change_percentage=24h"
    )
    return f"{COINGECKO_BASE}/coins/markets?{params}"


def _fetch_httpx(url: str, headers: dict) -> list[dict]:
    with httpx.Client(timeout=REQUEST_TIMEOUT, follow_redirects=True) as client:
        resp = client.get(url, headers=headers)
        resp.raise_for_status()
        return resp.json()


def _fetch_urllib(url: str, headers: dict) -> list[dict]:
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
        return json.loads(resp.read().decode())


def _http_get(url: str, headers: dict) -> list[dict]:
    if _HTTP_BACKEND == "httpx":
        return _fetch_httpx(url, headers)
    return _fetch_urllib(url, headers)


# ══════════════════════════════════════════════════════════════════════════════
#  Validation
# ══════════════════════════════════════════════════════════════════════════════

def _validate_coin(raw: dict, index: int) -> Optional[dict]:
    """
    Validate a single coin dict.
    Returns cleaned dict or None if invalid.
    """
    if _PYDANTIC:
        try:
            return CoinRaw(**raw).dict()
        except (ValidationError, TypeError) as exc:
            logger.warning("Coin[%d] validation failed: %s", index, exc)
            return None
    else:
        # Manual validation
        missing = REQUIRED_KEYS - set(raw.keys())
        if missing:
            logger.warning("Coin[%d] missing fields: %s", index, missing)
            return None
        # Remap to canonical names
        try:
            return {
                "id":                          str(raw["id"]),
                "symbol":                      str(raw["symbol"]),
                "name":                        str(raw["name"]),
                "current_price":               float(raw["current_price"] or 0),
                "market_cap":                  float(raw["market_cap"] or 0),
                "total_volume":                float(raw["total_volume"] or 0),
                "price_change_percentage_24h": float(raw.get("price_change_percentage_24h") or 0),
                "market_cap_rank":             int(raw.get("market_cap_rank") or 9999),
            }
        except (ValueError, TypeError) as exc:
            logger.warning("Coin[%d] coercion error: %s", index, exc)
            return None


def validate_response(data: Any) -> list[dict]:
    """
    Validate the full API response.
    Returns a list of valid coin dicts; raises ValueError if response is unusable.
    """
    if not isinstance(data, list):
        raise ValueError(f"Expected list from API, got {type(data).__name__}")
    if len(data) == 0:
        raise ValueError("API returned empty list — possible rate limit or outage")

    valid = []
    for i, item in enumerate(data):
        if not isinstance(item, dict):
            logger.warning("Item[%d] is not a dict, skipping", i)
            continue
        cleaned = _validate_coin(item, i)
        if cleaned is not None:
            valid.append(cleaned)

    if len(valid) == 0:
        raise ValueError("No valid coins after validation — aborting extract")

    drop_count = len(data) - len(valid)
    if drop_count > 0:
        logger.warning("Dropped %d invalid records (kept %d)", drop_count, len(valid))

    return valid


# ══════════════════════════════════════════════════════════════════════════════
#  Raw JSON persistence
# ══════════════════════════════════════════════════════════════════════════════

def _save_raw(data: list[dict], timestamp: datetime) -> Path:
    """
    Save raw API response to raw_data/<ISO_TIMESTAMP>.json
    Returns the path for logging / audit.
    """
    ts_str = timestamp.strftime("%Y%m%dT%H%M%SZ")
    path   = RAW_DIR / f"coingecko_{ts_str}.json"
    payload = {
        "extracted_at": timestamp.isoformat(),
        "coin_count":   len(data),
        "source":       "coingecko_markets",
        "data":         data,
    }
    path.write_text(json.dumps(payload, indent=2, default=str))
    logger.debug("Raw snapshot saved: %s", path)
    return path


# ══════════════════════════════════════════════════════════════════════════════
#  Main extract function
# ══════════════════════════════════════════════════════════════════════════════

def extract() -> tuple[list[dict], datetime]:
    """
    Extract top-N coins from CoinGecko.

    Returns:
        (validated_coins: list[dict], extracted_at: datetime)

    Raises:
        RuntimeError: if all retries exhausted
    """
    url     = _build_url()
    headers = _build_headers()
    extracted_at = datetime.now(tz=timezone.utc)
    last_exc: Exception | None = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            logger.info(
                "Extract attempt %d/%d — fetching top %d coins",
                attempt, MAX_RETRIES, TOP_N_COINS
            )
            raw_data = _http_get(url, headers)

            # Validate
            validated = validate_response(raw_data)
            logger.info("Extracted %d valid coins", len(validated))

            # Persist raw snapshot
            snapshot_path = _save_raw(raw_data, extracted_at)
            logger.info("Raw snapshot → %s", snapshot_path.name)

            return validated, extracted_at

        except (ValueError, RuntimeError) as exc:
            # Non-retryable: bad data shape
            logger.error("Non-retryable extract error: %s", exc)
            raise

        except Exception as exc:
            last_exc = exc
            wait = RETRY_BACKOFF ** attempt
            logger.warning(
                "Extract attempt %d failed: %s — retrying in %.1fs",
                attempt, exc, wait
            )
            if attempt < MAX_RETRIES:
                time.sleep(wait)

    raise RuntimeError(
        f"Extract failed after {MAX_RETRIES} attempts. Last error: {last_exc}"
    )


# ══════════════════════════════════════════════════════════════════════════════
#  Utility: list saved snapshots
# ══════════════════════════════════════════════════════════════════════════════

def list_raw_snapshots(limit: int = 10) -> list[Path]:
    """Return the N most recent raw snapshots."""
    snaps = sorted(RAW_DIR.glob("coingecko_*.json"), reverse=True)
    return snaps[:limit]


def load_raw_snapshot(path: Path) -> list[dict]:
    """Reload a raw snapshot for replay / backfill."""
    payload = json.loads(path.read_text())
    logger.info(
        "Loaded snapshot %s (%d coins, extracted %s)",
        path.name, payload["coin_count"], payload["extracted_at"]
    )
    return payload["data"]


# ══════════════════════════════════════════════════════════════════════════════
#  CLI test
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-8s %(message)s",
        datefmt="%H:%M:%S",
    )

    print("\n── Extract Test ───────────────────────────────────────")
    coins, ts = extract()

    print(f"\n✓ Extracted {len(coins)} coins at {ts.isoformat()}")
    print(f"\nTop 5 coins:")
    print(f"  {'Rank':<5} {'Symbol':<8} {'Name':<20} {'Price (USD)':>15}")
    print("  " + "─" * 52)
    for c in sorted(coins, key=lambda x: x["market_cap_rank"])[:5]:
        print(
            f"  {c['market_cap_rank']:<5} "
            f"{c['symbol'].upper():<8} "
            f"{c['name']:<20} "
            f"${c['current_price']:>14,.4f}"
        )

    snaps = list_raw_snapshots()
    print(f"\nRaw snapshots saved: {len(snaps)}")
    if snaps:
        print(f"  Latest: {snaps[0].name} ({snaps[0].stat().st_size:,} bytes)")
