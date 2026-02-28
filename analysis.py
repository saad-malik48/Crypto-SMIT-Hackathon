"""
analysis.py — Analytics & Query Layer
========================================
Responsibilities:
  • Run named SQL queries for the dashboard and reporting
  • Return clean Python dicts / DataFrames
  • Anomaly detection via Z-score on price_change_24h
  • Redis caching layer (optional) for expensive queries

Queries provided:
  1. top_gainers()          — Top 5 coins by 24h price change
  2. top_market_cap()       — Top 10 coins by market cap (latest snapshot)
  3. avg_market_cap()       — Average market cap across current snapshot
  4. total_market_value()   — Sum of all market caps
  5. volatility_ranking()   — Coins ranked by volatility_score DESC
  6. price_history(coin_id) — Time-series of price for one coin
  7. volume_comparison()    — Volume per coin (latest)
  8. detect_anomalies()     — Z-score anomaly detection on 24h changes
  9. kpi_summary()          — All dashboard KPIs in one call
"""

import logging
import math
import statistics
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

try:
    import pandas as pd
    _PANDAS = True
except ImportError:
    _PANDAS = False
    logger.info("pandas not installed — returning plain dicts")

try:
    import redis
    _REDIS = True
except ImportError:
    _REDIS = False

from config import REDIS_HOST, REDIS_PORT, REDIS_DB, REDIS_TTL, ZSCORE_THRESHOLD
from database import db, SQLiteManager


# ══════════════════════════════════════════════════════════════════════════════
#  Redis cache (optional)
# ══════════════════════════════════════════════════════════════════════════════

_redis_client = None

def _get_redis():
    global _redis_client
    if not _REDIS:
        return None
    if _redis_client is None:
        try:
            _redis_client = redis.Redis(
                host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB,
                decode_responses=True, socket_connect_timeout=2
            )
            _redis_client.ping()
            logger.debug("Redis connected")
        except Exception as exc:
            logger.warning("Redis unavailable (%s) — caching disabled", exc)
            _redis_client = None
    return _redis_client


import json, hashlib

def _cache_get(key: str):
    r = _get_redis()
    if r is None:
        return None
    try:
        val = r.get(key)
        return json.loads(val) if val else None
    except Exception:
        return None


def _cache_set(key: str, value, ttl: int = REDIS_TTL):
    r = _get_redis()
    if r is None:
        return
    try:
        r.setex(key, ttl, json.dumps(value, default=str))
    except Exception:
        pass


# ══════════════════════════════════════════════════════════════════════════════
#  SQL helpers
# ══════════════════════════════════════════════════════════════════════════════

def _is_sqlite() -> bool:
    return isinstance(db(), SQLiteManager)


def _fetchall(sql: str, params: tuple = ()) -> list[dict]:
    """Run a SELECT and return list of dicts."""
    manager = db()
    with manager.get_cursor() as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()
        if not rows:
            return []
        if isinstance(rows[0], dict):
            return [dict(r) for r in rows]
        # SQLite Row / tuple
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, r)) for r in rows]


def _fetchone(sql: str, params: tuple = ()) -> Optional[dict]:
    rows = _fetchall(sql, params)
    return rows[0] if rows else None


def _latest_ts_clause() -> str:
    """SQL fragment to filter to the latest extracted_at snapshot."""
    return "extracted_at = (SELECT MAX(extracted_at) FROM crypto_market)"


# ══════════════════════════════════════════════════════════════════════════════
#  Query 1: Top Gainers
# ══════════════════════════════════════════════════════════════════════════════

def top_gainers(limit: int = 5) -> list[dict]:
    """Top N coins by 24h price change % (latest snapshot)."""
    cache_key = f"top_gainers:{limit}"
    cached = _cache_get(cache_key)
    if cached:
        return cached

    sql = f"""
        SELECT coin_id, symbol, name, current_price, price_change_24h, market_cap_rank
        FROM crypto_market
        WHERE {_latest_ts_clause()}
        ORDER BY price_change_24h DESC
        LIMIT ?
    """ if _is_sqlite() else f"""
        SELECT coin_id, symbol, name, current_price, price_change_24h, market_cap_rank
        FROM crypto_market
        WHERE {_latest_ts_clause()}
        ORDER BY price_change_24h DESC
        LIMIT %s
    """
    result = _fetchall(sql, (limit,))
    _cache_set(cache_key, result, ttl=60)
    return result


# ══════════════════════════════════════════════════════════════════════════════
#  Query 2: Top Market Cap
# ══════════════════════════════════════════════════════════════════════════════

def top_market_cap(limit: int = 10) -> list[dict]:
    """Top N coins by market cap (latest snapshot)."""
    cache_key = f"top_mcap:{limit}"
    cached = _cache_get(cache_key)
    if cached:
        return cached

    sql = f"""
        SELECT coin_id, symbol, name, market_cap, current_price,
               market_cap_rank, price_change_24h
        FROM crypto_market
        WHERE {_latest_ts_clause()}
        ORDER BY market_cap DESC
        LIMIT {'?' if _is_sqlite() else '%s'}
    """
    result = _fetchall(sql, (limit,))
    _cache_set(cache_key, result)
    return result


# ══════════════════════════════════════════════════════════════════════════════
#  Query 3: Average Market Cap
# ══════════════════════════════════════════════════════════════════════════════

def avg_market_cap() -> float:
    """Average market cap across the latest snapshot."""
    sql = f"""
        SELECT AVG(market_cap) AS avg_mcap
        FROM crypto_market
        WHERE {_latest_ts_clause()}
    """
    row = _fetchone(sql)
    return float(row.get("avg_mcap") or 0) if row else 0.0


# ══════════════════════════════════════════════════════════════════════════════
#  Query 4: Total Market Value
# ══════════════════════════════════════════════════════════════════════════════

def total_market_value() -> float:
    """Sum of all market caps (latest snapshot)."""
    sql = f"""
        SELECT SUM(market_cap) AS total_mcap
        FROM crypto_market
        WHERE {_latest_ts_clause()}
    """
    row = _fetchone(sql)
    return float(row.get("total_mcap") or 0) if row else 0.0


# ══════════════════════════════════════════════════════════════════════════════
#  Query 5: Volatility Ranking
# ══════════════════════════════════════════════════════════════════════════════

def volatility_ranking(limit: int = 10) -> list[dict]:
    """Coins ranked by volatility_score DESC (latest snapshot)."""
    sql = f"""
        SELECT coin_id, symbol, name, volatility_score,
               price_change_24h, total_volume
        FROM crypto_market
        WHERE {_latest_ts_clause()}
        ORDER BY volatility_score DESC
        LIMIT {'?' if _is_sqlite() else '%s'}
    """
    return _fetchall(sql, (limit,))


# ══════════════════════════════════════════════════════════════════════════════
#  Query 6: Price History
# ══════════════════════════════════════════════════════════════════════════════

def price_history(coin_id: str, limit: int = 100) -> list[dict]:
    """
    Time-series of price for a given coin, oldest→newest.
    Returns list of {extracted_at, current_price, price_change_24h}
    """
    sql = """
        SELECT extracted_at, current_price, price_change_24h, total_volume
        FROM crypto_market
        WHERE coin_id = {}
        ORDER BY extracted_at ASC
        LIMIT {}
    """.format(
        "?" if _is_sqlite() else "%s",
        "?" if _is_sqlite() else "%s",
    )
    return _fetchall(sql, (coin_id, limit))


# ══════════════════════════════════════════════════════════════════════════════
#  Query 7: Volume Comparison
# ══════════════════════════════════════════════════════════════════════════════

def volume_comparison() -> list[dict]:
    """24h total volume per coin (latest snapshot), sorted descending."""
    sql = f"""
        SELECT symbol, name, total_volume, current_price, price_change_24h
        FROM crypto_market
        WHERE {_latest_ts_clause()}
        ORDER BY total_volume DESC
    """
    return _fetchall(sql)


# ══════════════════════════════════════════════════════════════════════════════
#  Query 8: Anomaly Detection (Z-score)
# ══════════════════════════════════════════════════════════════════════════════

def detect_anomalies(threshold: float = ZSCORE_THRESHOLD) -> list[dict]:
    """
    Flag coins whose price_change_24h is statistically anomalous.

    Method: Z-score = (x - μ) / σ
    Any coin with |z| > threshold is flagged as an anomaly.

    Returns list of {symbol, name, price_change_24h, z_score, anomaly_type}
    """
    sql = f"""
        SELECT symbol, name, price_change_24h, current_price, total_volume
        FROM crypto_market
        WHERE {_latest_ts_clause()}
    """
    rows = _fetchall(sql)
    if len(rows) < 3:
        return []

    changes = [float(r["price_change_24h"]) for r in rows]
    mu    = statistics.mean(changes)
    sigma = statistics.stdev(changes) or 1.0  # avoid divide-by-zero

    anomalies = []
    for r in rows:
        z = (float(r["price_change_24h"]) - mu) / sigma
        if abs(z) >= threshold:
            anomalies.append({
                "symbol":           r["symbol"],
                "name":             r["name"],
                "price_change_24h": round(float(r["price_change_24h"]), 4),
                "current_price":    float(r["current_price"]),
                "z_score":          round(z, 3),
                "anomaly_type":     "spike" if z > 0 else "crash",
            })

    anomalies.sort(key=lambda x: abs(x["z_score"]), reverse=True)
    logger.info("Anomaly scan: %d anomalies detected (threshold=%.1f)", len(anomalies), threshold)
    return anomalies


# ══════════════════════════════════════════════════════════════════════════════
#  Query 9: KPI Summary (dashboard main call)
# ══════════════════════════════════════════════════════════════════════════════

def kpi_summary() -> dict:
    """
    Compute all dashboard KPIs in one call.
    Returns a dict suitable for Streamlit KPI cards.
    """
    cache_key = "kpi_summary"
    cached = _cache_get(cache_key)
    if cached:
        return cached

    total_mcap = total_market_value()
    avg_mcap   = avg_market_cap()

    gainers    = top_gainers(1)
    volatile   = volatility_ranking(1)
    top_coins  = top_market_cap(10)

    avg_price  = (
        sum(c["current_price"] for c in top_coins) / len(top_coins)
        if top_coins else 0
    )

    result = {
        "total_market_cap":    total_mcap,
        "avg_market_cap":      avg_mcap,
        "avg_price_top10":     avg_price,
        "highest_gainer":      gainers[0] if gainers else {},
        "most_volatile":       volatile[0] if volatile else {},
        "computed_at":         datetime.now(tz=timezone.utc).isoformat(),
    }

    _cache_set(cache_key, result, ttl=55)   # slightly under ETL interval
    return result


# ══════════════════════════════════════════════════════════════════════════════
#  Optional: return pandas DataFrames
# ══════════════════════════════════════════════════════════════════════════════

def get_market_df() -> "pd.DataFrame":
    """Return full latest snapshot as a pandas DataFrame."""
    if not _PANDAS:
        raise ImportError("pandas not installed")
    sql = f"""
        SELECT *
        FROM crypto_market
        WHERE {_latest_ts_clause()}
        ORDER BY market_cap_rank
    """
    rows = _fetchall(sql)
    return pd.DataFrame(rows)


def get_history_df(coin_id: str, limit: int = 200) -> "pd.DataFrame":
    """Return price history for a coin as a pandas DataFrame."""
    if not _PANDAS:
        raise ImportError("pandas not installed")
    rows = price_history(coin_id, limit)
    df = pd.DataFrame(rows)
    if not df.empty:
        df["extracted_at"] = pd.to_datetime(df["extracted_at"])
        df = df.sort_values("extracted_at")
    return df


# ══════════════════════════════════════════════════════════════════════════════
#  CLI test
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-8s %(message)s",
        datefmt="%H:%M:%S",
    )

    def _fmt_usd(v): return f"${v:>20,.0f}"
    def _section(title): print(f"\n{'─'*55}\n  {title}\n{'─'*55}")

    _section("KPI Summary")
    kpi = kpi_summary()
    print(f"  Total Market Cap : {_fmt_usd(kpi['total_market_cap'])}")
    print(f"  Avg Market Cap   : {_fmt_usd(kpi['avg_market_cap'])}")
    print(f"  Avg Price Top10  : ${kpi['avg_price_top10']:>12,.2f}")
    if kpi["highest_gainer"]:
        g = kpi["highest_gainer"]
        print(f"  Top Gainer       :  {g.get('symbol','?')}  {g.get('price_change_24h',0):+.2f}%")
    if kpi["most_volatile"]:
        v = kpi["most_volatile"]
        print(f"  Most Volatile    :  {v.get('symbol','?')}  score={v.get('volatility_score',0):,.0f}")

    _section("Top 5 by Market Cap")
    for c in top_market_cap(5):
        print(f"  {c.get('market_cap_rank','?'):>4}.  {c.get('symbol','?'):<8}  mcap={_fmt_usd(c.get('market_cap',0))}")

    _section("Top 5 Gainers")
    for c in top_gainers(5):
        print(f"  {c.get('symbol','?'):<8}  {c.get('price_change_24h',0):+8.2f}%  ${c.get('current_price',0):>12,.4f}")

    _section("Volatility Ranking")
    for c in volatility_ranking(5):
        print(f"  {c.get('symbol','?'):<8}  score={c.get('volatility_score',0):>20,.0f}  chg={c.get('price_change_24h',0):+.2f}%")

    _section("Anomaly Detection (Z-score ≥ 2.5)")
    anomalies = detect_anomalies()
    if anomalies:
        for a in anomalies:
            print(f"  ⚠  {a['symbol']:<8}  z={a['z_score']:+.2f}  ({a['anomaly_type']})  chg={a['price_change_24h']:+.2f}%")
    else:
        print("  No anomalies detected in current snapshot")
