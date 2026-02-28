"""
config.py — Centralized configuration for Crypto Analytics Platform
Loads from environment variables with sensible defaults.
"""

import os
from pathlib import Path

# ─── Base Paths ───────────────────────────────────────────────────────────────
BASE_DIR   = Path(__file__).parent
LOGS_DIR   = BASE_DIR / "logs"
RAW_DIR    = BASE_DIR / "raw_data"

LOGS_DIR.mkdir(exist_ok=True)
RAW_DIR.mkdir(exist_ok=True)

# ─── PostgreSQL ───────────────────────────────────────────────────────────────
DB_CONFIG = {
    "host":     os.getenv("DB_HOST",     "localhost"),
    "port":     int(os.getenv("DB_PORT", "5432")),
    "database": os.getenv("DB_NAME",     "crypto_analytics"),
    "user":     os.getenv("DB_USER",     "postgres"),
    "password": os.getenv("DB_PASSWORD", "postgres"),
}

DATABASE_URL = (
    f"postgresql://{DB_CONFIG['user']}:{DB_CONFIG['password']}"
    f"@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}"
)

# ─── Redis (optional caching) ─────────────────────────────────────────────────
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_DB   = int(os.getenv("REDIS_DB",   "0"))
REDIS_TTL  = int(os.getenv("REDIS_TTL",  "300"))   # 5 minutes

# ─── CoinGecko API ───────────────────────────────────────────────────────────
COINGECKO_BASE  = "https://api.coingecko.com/api/v3"
COINGECKO_KEY   = os.getenv("COINGECKO_API_KEY", "")   # optional pro key
TOP_N_COINS     = int(os.getenv("TOP_N_COINS", "20"))
COINS_VS        = "usd"

# ─── ETL Pipeline ────────────────────────────────────────────────────────────
ETL_INTERVAL_MINUTES = int(os.getenv("ETL_INTERVAL_MINUTES", "5"))
BATCH_SIZE           = int(os.getenv("BATCH_SIZE", "50"))
REQUEST_TIMEOUT      = int(os.getenv("REQUEST_TIMEOUT", "30"))
MAX_RETRIES          = int(os.getenv("MAX_RETRIES", "3"))
RETRY_BACKOFF        = float(os.getenv("RETRY_BACKOFF", "2.0"))

# ─── Streamlit Dashboard ──────────────────────────────────────────────────────
DASHBOARD_REFRESH_SECONDS = int(os.getenv("DASHBOARD_REFRESH", "60"))
DASHBOARD_PORT            = int(os.getenv("DASHBOARD_PORT", "8501"))

# ─── Anomaly Detection ───────────────────────────────────────────────────────
ZSCORE_THRESHOLD = float(os.getenv("ZSCORE_THRESHOLD", "2.5"))
