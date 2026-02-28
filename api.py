"""
api.py — FastAPI REST API
===========================
Exposes all analytics queries as a clean REST API.
Auto-generates interactive docs at /docs (Swagger UI).

Endpoints:
  GET /health                    — health check
  GET /api/v1/prices             — latest snapshot (all coins)
  GET /api/v1/gainers?limit=5    — top gainers
  GET /api/v1/market-cap?limit=10 — top by market cap
  GET /api/v1/volume             — volume comparison
  GET /api/v1/volatility?limit=10 — volatility ranking
  GET /api/v1/history/{coin_id}  — price history
  GET /api/v1/anomalies          — anomaly detection
  GET /api/v1/kpis               — full KPI summary
  POST /api/v1/etl/trigger       — manually trigger ETL run
"""

import logging
from datetime import datetime, timezone
from typing import Optional

try:
    from fastapi import FastAPI, HTTPException, Query, BackgroundTasks
    from fastapi.middleware.cors import CORSMiddleware
    import uvicorn
except ImportError:
    print("Run: pip install fastapi uvicorn")
    raise

from analysis import (
    top_gainers, top_market_cap, volume_comparison,
    volatility_ranking, detect_anomalies, kpi_summary, price_history,
)
from load import get_row_count, get_latest_snapshot
from etl_pipeline import run_once
from config import ZSCORE_THRESHOLD

logger = logging.getLogger(__name__)

# ─── App ──────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Crypto Analytics API",
    description="Real-Time Cryptocurrency Analytics Platform",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _ok(data, meta: dict | None = None):
    return {
        "status": "ok",
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        "data": data,
        **(meta or {}),
    }


@app.get("/health")
def health():
    return {"status": "ok", "service": "crypto-analytics-api", "db_records": get_row_count()}


@app.get("/api/v1/prices")
def latest_prices():
    """Full latest snapshot for all tracked coins."""
    data = get_latest_snapshot()
    return _ok(data, {"count": len(data)})


@app.get("/api/v1/gainers")
def gainers(limit: int = Query(5, ge=1, le=20)):
    return _ok(top_gainers(limit))


@app.get("/api/v1/market-cap")
def market_cap(limit: int = Query(10, ge=1, le=20)):
    return _ok(top_market_cap(limit))


@app.get("/api/v1/volume")
def volume():
    return _ok(volume_comparison())


@app.get("/api/v1/volatility")
def volatility(limit: int = Query(10, ge=1, le=20)):
    return _ok(volatility_ranking(limit))


@app.get("/api/v1/history/{coin_id}")
def history(coin_id: str, limit: int = Query(100, ge=1, le=500)):
    data = price_history(coin_id.lower(), limit)
    if not data:
        raise HTTPException(404, f"No history found for '{coin_id}'")
    return _ok(data, {"coin_id": coin_id, "count": len(data)})


@app.get("/api/v1/anomalies")
def anomalies(threshold: float = Query(ZSCORE_THRESHOLD, ge=1.0, le=5.0)):
    return _ok(detect_anomalies(threshold))


@app.get("/api/v1/kpis")
def kpis():
    return _ok(kpi_summary())


@app.post("/api/v1/etl/trigger")
def trigger_etl(background_tasks: BackgroundTasks):
    """Manually trigger one ETL run (non-blocking)."""
    background_tasks.add_task(run_once)
    return {"status": "ok", "message": "ETL run triggered in background"}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=False)
