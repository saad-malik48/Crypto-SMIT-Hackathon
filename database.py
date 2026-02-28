"""
database.py — PostgreSQL Database Layer
========================================
Responsibilities:
  • Manage connection pool (psycopg2 + connection pool)
  • Create schema: crypto_market table + indexes
  • Provide context-manager helpers for safe transactions
  • Offer a lightweight SQLite fallback for local development

Design choices:
  • SimpleConnectionPool over thread-local connections for thread safety
  • TIMESTAMPTZ for timezone-aware storage
  • Composite index on (coin_id, extracted_at) for time-series queries
  • UPSERT key on (coin_id, extracted_at) prevents duplicate runs
"""

import logging
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Generator

logger = logging.getLogger(__name__)

# ─── Try psycopg2 (Postgres) else fall back to sqlite3 ───────────────────────
try:
    import psycopg2
    import psycopg2.pool
    import psycopg2.extras
    POSTGRES_AVAILABLE = True
except ImportError:
    POSTGRES_AVAILABLE = False
    logger.warning("psycopg2 not installed — using SQLite fallback")

from config import DB_CONFIG, BASE_DIR


# ══════════════════════════════════════════════════════════════════════════════
#  Schema DDL
# ══════════════════════════════════════════════════════════════════════════════

POSTGRES_DDL = """
-- Main market data table
CREATE TABLE IF NOT EXISTS crypto_market (
    id                BIGSERIAL PRIMARY KEY,
    coin_id           VARCHAR(100)     NOT NULL,          -- e.g. "bitcoin"
    symbol            VARCHAR(20)      NOT NULL,          -- e.g. "btc"
    name              VARCHAR(200)     NOT NULL,          -- e.g. "Bitcoin"
    current_price     NUMERIC(24, 8)   NOT NULL,
    market_cap        NUMERIC(30, 2),
    total_volume      NUMERIC(30, 2),
    price_change_24h  NUMERIC(10, 4),                     -- percentage
    market_cap_rank   INTEGER,
    volatility_score  NUMERIC(40, 4),                     -- abs(price_change) * volume
    extracted_at      TIMESTAMPTZ      NOT NULL DEFAULT NOW(),

    -- Prevent duplicate ETL runs per coin per timestamp bucket
    CONSTRAINT uq_coin_ts UNIQUE (coin_id, extracted_at)
);

-- Index for per-coin time-series lookups
CREATE INDEX IF NOT EXISTS idx_coin_id
    ON crypto_market (coin_id);

-- Index for time-range queries / dashboard filtering
CREATE INDEX IF NOT EXISTS idx_extracted_at
    ON crypto_market (extracted_at DESC);

-- Composite index for time-series per coin (most common query pattern)
CREATE INDEX IF NOT EXISTS idx_coin_ts
    ON crypto_market (coin_id, extracted_at DESC);

-- Index for ranking queries
CREATE INDEX IF NOT EXISTS idx_market_cap_rank
    ON crypto_market (market_cap_rank)
    WHERE market_cap_rank IS NOT NULL;
"""

SQLITE_DDL = """
CREATE TABLE IF NOT EXISTS crypto_market (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    coin_id           TEXT     NOT NULL,
    symbol            TEXT     NOT NULL,
    name              TEXT     NOT NULL,
    current_price     REAL     NOT NULL,
    market_cap        REAL,
    total_volume      REAL,
    price_change_24h  REAL,
    market_cap_rank   INTEGER,
    volatility_score  REAL,
    extracted_at      TEXT     NOT NULL,
    UNIQUE(coin_id, extracted_at)
);
CREATE INDEX IF NOT EXISTS idx_coin_id      ON crypto_market (coin_id);
CREATE INDEX IF NOT EXISTS idx_extracted_at ON crypto_market (extracted_at DESC);
CREATE INDEX IF NOT EXISTS idx_coin_ts      ON crypto_market (coin_id, extracted_at DESC);
"""

SQLITE_PATH = BASE_DIR / "data" / "crypto_analytics.db"


# ══════════════════════════════════════════════════════════════════════════════
#  PostgreSQL Manager
# ══════════════════════════════════════════════════════════════════════════════

class PostgresManager:
    """Thread-safe connection pool wrapping psycopg2."""

    _pool: "psycopg2.pool.SimpleConnectionPool | None" = None

    def __init__(self, minconn: int = 1, maxconn: int = 10):
        self.minconn = minconn
        self.maxconn = maxconn

    def init_pool(self) -> None:
        if not POSTGRES_AVAILABLE:
            raise RuntimeError("psycopg2 not installed")
        if self._pool is None:
            self._pool = psycopg2.pool.SimpleConnectionPool(
                self.minconn,
                self.maxconn,
                **DB_CONFIG
            )
            logger.info(
                "PostgreSQL pool created (%d–%d connections)", self.minconn, self.maxconn
            )

    def close_pool(self) -> None:
        if self._pool:
            self._pool.closeall()
            self._pool = None
            logger.info("PostgreSQL pool closed")

    @contextmanager
    def get_connection(self) -> Generator:
        """Yield a connection, return it to pool on exit."""
        if self._pool is None:
            self.init_pool()
        conn = self._pool.getconn()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            self._pool.putconn(conn)

    @contextmanager
    def get_cursor(self, cursor_factory=None):
        """Yield a DictCursor, commit/rollback automatically."""
        with self.get_connection() as conn:
            factory = cursor_factory or psycopg2.extras.RealDictCursor
            with conn.cursor(cursor_factory=factory) as cur:
                yield cur

    def create_schema(self) -> None:
        """Run DDL to create tables and indexes (idempotent)."""
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(POSTGRES_DDL)
        logger.info("PostgreSQL schema initialized")

    def test_connection(self) -> bool:
        try:
            with self.get_cursor() as cur:
                cur.execute("SELECT version()")
                version = cur.fetchone()
                logger.info("Connected to PostgreSQL: %s", dict(version)["version"][:60])
            return True
        except Exception as exc:
            logger.error("PostgreSQL connection failed: %s", exc)
            return False


# ══════════════════════════════════════════════════════════════════════════════
#  SQLite Fallback Manager
# ══════════════════════════════════════════════════════════════════════════════

class SQLiteManager:
    """SQLite backend for local development / CI without Postgres."""

    def __init__(self, path: Path = SQLITE_PATH):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        return conn

    @contextmanager
    def get_connection(self) -> Generator:
        conn = self._connect()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    @contextmanager
    def get_cursor(self, **_):
        with self.get_connection() as conn:
            cur = conn.cursor()
            yield cur

    def create_schema(self) -> None:
        with self.get_connection() as conn:
            conn.executescript(SQLITE_DDL)
        logger.info("SQLite schema initialized at %s", self.path)

    def test_connection(self) -> bool:
        try:
            with self.get_cursor() as cur:
                cur.execute("SELECT sqlite_version()")
                ver = cur.fetchone()[0]
                logger.info("Connected to SQLite %s", ver)
            return True
        except Exception as exc:
            logger.error("SQLite connection failed: %s", exc)
            return False


# ══════════════════════════════════════════════════════════════════════════════
#  Factory — auto-detect backend
# ══════════════════════════════════════════════════════════════════════════════

def get_db_manager(force_sqlite: bool = False):
    """Return the best available DB manager."""
    if force_sqlite or not POSTGRES_AVAILABLE:
        mgr = SQLiteManager()
    else:
        mgr = PostgresManager()
        # Probe the connection; fall back to SQLite on failure
        try:
            mgr.init_pool()
            if not mgr.test_connection():
                raise ConnectionError("Probe failed")
        except Exception as exc:
            logger.warning("Postgres unavailable (%s) — falling back to SQLite", exc)
            mgr = SQLiteManager()

    mgr.create_schema()
    return mgr


# ══════════════════════════════════════════════════════════════════════════════
#  Module-level singleton
# ══════════════════════════════════════════════════════════════════════════════

_db_manager = None

def db() -> "PostgresManager | SQLiteManager":
    """Return the module-level DB manager singleton."""
    global _db_manager
    if _db_manager is None:
        _db_manager = get_db_manager()
    return _db_manager


# ══════════════════════════════════════════════════════════════════════════════
#  CLI test
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    force = "--sqlite" in sys.argv
    manager = get_db_manager(force_sqlite=force)

    print("\n✓ Database initialized successfully")
    print(f"  Backend : {'SQLite' if isinstance(manager, SQLiteManager) else 'PostgreSQL'}")
    print(f"  Schema  : crypto_market + 4 indexes")

    # Quick sanity query
    with manager.get_cursor() as cur:
        if isinstance(manager, SQLiteManager):
            cur.execute("SELECT COUNT(*) FROM crypto_market")
        else:
            cur.execute("SELECT COUNT(*) FROM crypto_market")
        row = cur.fetchone()
        count = row[0] if isinstance(row, (tuple, list)) else list(row.values())[0]
        print(f"  Rows    : {count}")
