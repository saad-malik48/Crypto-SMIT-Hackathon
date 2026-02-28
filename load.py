"""
load.py — ETL Load Layer
==========================
Responsibilities:
  • Accept a list of TransformedCoin records
  • Insert into crypto_market with UPSERT (ON CONFLICT DO UPDATE)
  • Use batch inserts for efficiency (executemany / execute_values)
  • Wrap each batch in a single transaction
  • Return a LoadResult summary for the orchestrator
  • Support both PostgreSQL and SQLite

Design choices:
  • UPSERT key = (coin_id, extracted_at) — idempotent re-runs
  • psycopg2.extras.execute_values for fast bulk Postgres inserts
  • SQLite uses executemany with INSERT OR REPLACE
  • Configurable BATCH_SIZE to avoid oversized transactions
  • LoadResult dataclass carries inserted/updated counts back to orchestrator
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)

try:
    import psycopg2.extras
    _PG = True
except ImportError:
    _PG = False

from config import BATCH_SIZE
from database import db, PostgresManager, SQLiteManager
from transform import TransformedCoin


# ══════════════════════════════════════════════════════════════════════════════
#  Result dataclass
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class LoadResult:
    total:       int = 0
    inserted:    int = 0
    updated:     int = 0
    failed:      int = 0
    duration_ms: float = 0.0

    @property
    def success_rate(self) -> float:
        if self.total == 0:
            return 0.0
        return (self.inserted + self.updated) / self.total * 100

    def __str__(self) -> str:
        return (
            f"LoadResult(total={self.total}, inserted={self.inserted}, "
            f"updated={self.updated}, failed={self.failed}, "
            f"success={self.success_rate:.1f}%, dur={self.duration_ms:.0f}ms)"
        )


# ══════════════════════════════════════════════════════════════════════════════
#  Row builders
# ══════════════════════════════════════════════════════════════════════════════

def _coin_to_tuple(coin: TransformedCoin) -> tuple:
    """Convert TransformedCoin to a tuple matching INSERT column order."""
    return (
        coin.coin_id,
        coin.symbol,
        coin.name,
        coin.current_price,
        coin.market_cap,
        coin.total_volume,
        coin.price_change_24h,
        coin.market_cap_rank,
        coin.volatility_score,
        coin.extracted_at,
    )


# ══════════════════════════════════════════════════════════════════════════════
#  PostgreSQL load
# ══════════════════════════════════════════════════════════════════════════════

_PG_UPSERT = """
    INSERT INTO crypto_market
        (coin_id, symbol, name, current_price, market_cap, total_volume,
         price_change_24h, market_cap_rank, volatility_score, extracted_at)
    VALUES %s
    ON CONFLICT (coin_id, extracted_at)
    DO UPDATE SET
        symbol            = EXCLUDED.symbol,
        name              = EXCLUDED.name,
        current_price     = EXCLUDED.current_price,
        market_cap        = EXCLUDED.market_cap,
        total_volume      = EXCLUDED.total_volume,
        price_change_24h  = EXCLUDED.price_change_24h,
        market_cap_rank   = EXCLUDED.market_cap_rank,
        volatility_score  = EXCLUDED.volatility_score
"""

_PG_TEMPLATE = "(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"


def _load_postgres(manager: "PostgresManager", batches: list[list[tuple]]) -> LoadResult:
    result = LoadResult()
    import time
    t0 = time.perf_counter()

    with manager.get_connection() as conn:
        with conn.cursor() as cur:
            for batch in batches:
                try:
                    before = cur.rowcount
                    psycopg2.extras.execute_values(
                        cur, _PG_UPSERT, batch, template=_PG_TEMPLATE, page_size=len(batch)
                    )
                    result.total    += len(batch)
                    result.inserted += cur.rowcount  # rows affected
                    logger.debug("Batch of %d rows upserted (rowcount=%d)", len(batch), cur.rowcount)
                except Exception as exc:
                    logger.error("Batch load failed: %s", exc)
                    result.failed += len(batch)
                    conn.rollback()

    result.duration_ms = (time.perf_counter() - t0) * 1000
    return result


# ══════════════════════════════════════════════════════════════════════════════
#  SQLite load
# ══════════════════════════════════════════════════════════════════════════════

_SQLITE_UPSERT = """
    INSERT OR REPLACE INTO crypto_market
        (coin_id, symbol, name, current_price, market_cap, total_volume,
         price_change_24h, market_cap_rank, volatility_score, extracted_at)
    VALUES (?,?,?,?,?,?,?,?,?,?)
"""


def _load_sqlite(manager: "SQLiteManager", batches: list[list[tuple]]) -> LoadResult:
    result = LoadResult()
    import time
    t0 = time.perf_counter()

    with manager.get_connection() as conn:
        cur = conn.cursor()
        for batch in batches:
            # SQLite executemany handles each row's INSERT OR REPLACE
            sqlite_batch = [
                row[:-1] + (row[-1].isoformat() if isinstance(row[-1], datetime) else row[-1],)
                for row in batch
            ]
            try:
                cur.executemany(_SQLITE_UPSERT, sqlite_batch)
                result.total    += len(batch)
                result.inserted += cur.rowcount
            except Exception as exc:
                logger.error("SQLite batch failed: %s", exc)
                result.failed += len(batch)

    result.duration_ms = (time.perf_counter() - t0) * 1000
    return result


# ══════════════════════════════════════════════════════════════════════════════
#  Public load function
# ══════════════════════════════════════════════════════════════════════════════

def load(coins: list[TransformedCoin], batch_size: int = BATCH_SIZE) -> LoadResult:
    """
    Load a list of TransformedCoin records into the database.

    Args:
        coins:      Output from transform.transform()
        batch_size: Number of rows per INSERT batch

    Returns:
        LoadResult with insert/update/failure counts
    """
    if not coins:
        logger.warning("load() called with empty list — nothing to do")
        return LoadResult()

    # Build row tuples
    rows = [_coin_to_tuple(c) for c in coins]

    # Split into batches
    batches = [rows[i: i + batch_size] for i in range(0, len(rows), batch_size)]
    logger.info(
        "Loading %d coins in %d batch(es) (batch_size=%d)",
        len(coins), len(batches), batch_size
    )

    manager = db()

    if isinstance(manager, PostgresManager) and _PG:
        result = _load_postgres(manager, batches)
    else:
        result = _load_sqlite(manager, batches)

    logger.info("Load complete: %s", result)
    return result


# ══════════════════════════════════════════════════════════════════════════════
#  Utility: row count query
# ══════════════════════════════════════════════════════════════════════════════

def get_row_count() -> int:
    """Quick count of all rows in crypto_market."""
    manager = db()
    with manager.get_cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM crypto_market")
        row = cur.fetchone()
        if isinstance(row, dict):
            return list(row.values())[0]
        return row[0]


def get_latest_snapshot() -> list[dict]:
    """Return the most recently extracted set of coins."""
    manager = db()
    sql = """
        SELECT * FROM crypto_market
        WHERE extracted_at = (SELECT MAX(extracted_at) FROM crypto_market)
        ORDER BY market_cap_rank
    """
    with manager.get_cursor() as cur:
        cur.execute(sql)
        rows = cur.fetchall()
        return [dict(r) for r in rows]


# ══════════════════════════════════════════════════════════════════════════════
#  CLI test
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import logging
    from datetime import timezone
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-8s %(message)s",
        datefmt="%H:%M:%S",
    )
    from transform import TransformedCoin

    now = datetime.now(tz=timezone.utc)

    # Build sample records
    sample_coins = [
        TransformedCoin(
            coin_id="bitcoin", symbol="BTC", name="Bitcoin",
            current_price=67_432.10, market_cap=1_328_000_000_000,
            total_volume=28_500_000_000, price_change_24h=2.34,
            market_cap_rank=1, volatility_score=66_690_000_000.0,
            extracted_at=now,
        ),
        TransformedCoin(
            coin_id="ethereum", symbol="ETH", name="Ethereum",
            current_price=3_812.50, market_cap=457_000_000_000,
            total_volume=15_200_000_000, price_change_24h=-1.87,
            market_cap_rank=2, volatility_score=28_424_000_000.0,
            extracted_at=now,
        ),
        TransformedCoin(
            coin_id="solana", symbol="SOL", name="Solana",
            current_price=178.40, market_cap=78_500_000_000,
            total_volume=3_400_000_000, price_change_24h=5.61,
            market_cap_rank=5, volatility_score=19_074_000_000.0,
            extracted_at=now,
        ),
    ]

    print("\n── Load Test ──────────────────────────────────────────")
    result = load(sample_coins, batch_size=10)
    print(f"\n✓ {result}")
    print(f"\n  Total rows in DB: {get_row_count():,}")

    snapshot = get_latest_snapshot()
    print(f"\nLatest snapshot ({len(snapshot)} coins):")
    for row in snapshot[:3]:
        print(f"  {row.get('market_cap_rank', '?'):>4}. {row.get('symbol','?'):<8}  ${row.get('current_price',0):>12,.2f}")

    # Test idempotency: load same coins again → should UPSERT, not duplicate
    print("\n── Idempotency test (re-load same records) ────────────")
    result2 = load(sample_coins, batch_size=10)
    count2 = get_row_count()
    print(f"✓ Row count after re-load: {count2:,} (should be same as before)")
