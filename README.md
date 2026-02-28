# CRYPTEX — Real-Time Crypto Analytics Platform

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://share.streamlit.io/)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

```
  ╔══════════════════════════════════════════════════════════╗
  ║   ETL Pipeline · PostgreSQL · CoinGecko · Streamlit     ║
  ║   FastAPI · Redis · Docker · Anomaly Detection          ║
  ╚══════════════════════════════════════════════════════════╝
```

> 🚀 **Live Demo:** [Deploy your own in 2 minutes!](streamlit_cloud.md)

A production-ready cryptocurrency analytics platform featuring real-time data ingestion, transformation, and visualization with anomaly detection.

## Architecture

```
CoinGecko API
     │
     ▼
┌─────────────────────────────────────────────────────────┐
│                    ETL PIPELINE                          │
│                                                          │
│  extract.py ──► transform.py ──► load.py                │
│  (fetch+validate) (clean+enrich) (UPSERT batch)         │
│       │                │               │                 │
│  raw_data/json    volatility_score  PostgreSQL           │
│                   extracted_at      (or SQLite)          │
└──────────────────────────┬──────────────────────────────┘
                           │ every 5 min (APScheduler)
                           │
           ┌───────────────┼──────────────────┐
           │               │                  │
     ┌─────▼──────┐  ┌────▼────────┐  ┌──────▼────────┐
     │ analysis.py│  │  Redis      │  │  FastAPI       │
     │            │  │  Cache      │  │  REST API      │
     │ Top gainers│  │  (55s TTL)  │  │  /api/v1/...  │
     │ Market cap │  └─────────────┘  └───────────────┘
     │ Volatility │
     │ Anomalies  │
     └─────┬──────┘
           │
     ┌─────▼──────────────────────────────────┐
     │        Streamlit Dashboard              │
     │                                         │
     │  KPI Cards · Bar Charts · Line Charts  │
     │  Heatmap · Anomaly Alerts · Table      │
     │  Auto-refresh every 60s                │
     └────────────────────────────────────────┘
```

## Project Structure

```
crypto_analytics/
├── config.py          ← All env-var config, single source of truth
├── database.py        ← Connection pool, schema DDL, SQLite fallback
├── extract.py         ← CoinGecko API, validation, raw JSON snapshots
├── transform.py       ← Cleaning, type coercion, volatility_score
├── load.py            ← UPSERT batch insert, transaction handling
├── etl_pipeline.py    ← Orchestrator + APScheduler, circuit breaker
├── analysis.py        ← SQL queries, Z-score anomaly detection, Redis cache
├── dashboard.py       ← Streamlit live dashboard
├── api.py             ← FastAPI REST endpoints
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── tests/
│   └── test_platform.py   ← pytest unit + integration tests
├── logs/                  ← ETL run logs
└── raw_data/              ← Raw CoinGecko JSON snapshots
```

## Quick Start (Local, SQLite)

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run ETL once (uses SQLite automatically if Postgres unavailable)
python etl_pipeline.py --once

# 3. Launch dashboard
streamlit run dashboard.py

# 4. (Optional) Launch REST API
python api.py
```

## With PostgreSQL

```bash
# Set environment variables
export DB_HOST=localhost
export DB_PORT=5432
export DB_NAME=crypto_analytics
export DB_USER=postgres
export DB_PASSWORD=yourpassword

# Initialize schema
python database.py

# Run ETL continuously
python etl_pipeline.py

# In another terminal
streamlit run dashboard.py
```

## Docker (Full Stack)

```bash
# Start everything: Postgres + Redis + ETL + Dashboard + API
docker-compose up -d

# View logs
docker-compose logs -f etl

# Access
#   Dashboard → http://localhost:8501
#   API Docs  → http://localhost:8000/docs
```

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `DB_HOST` | localhost | PostgreSQL host |
| `DB_PORT` | 5432 | PostgreSQL port |
| `DB_NAME` | crypto_analytics | Database name |
| `DB_USER` | postgres | DB username |
| `DB_PASSWORD` | postgres | DB password |
| `REDIS_HOST` | localhost | Redis host |
| `REDIS_TTL` | 300 | Cache TTL seconds |
| `ETL_INTERVAL_MINUTES` | 5 | Pipeline frequency |
| `TOP_N_COINS` | 20 | Coins to track |
| `ZSCORE_THRESHOLD` | 2.5 | Anomaly detection sensitivity |
| `COINGECKO_API_KEY` | — | Optional Pro API key |

## Run Tests

```bash
pytest tests/ -v --tb=short --cov=. --cov-report=term-missing
```

## 🚀 Deployment

**⚠️ Important:** This is a Python Streamlit app. It will NOT work on Vercel or Netlify (they're for static sites only).

**✅ Recommended Platform: Streamlit Cloud (FREE)**

Deploy in 2 minutes:
1. Go to https://share.streamlit.io/
2. Sign in with GitHub
3. Deploy `dashboard.py` from this repo
4. Done! Get your live URL

**Other Options:**
- **[Streamlit Cloud Guide](DEPLOY_STREAMLIT_CLOUD.md)** - Step-by-step (FREE)
- **[Why Not Vercel/Netlify?](VERCEL_NETLIFY_ISSUE.md)** - Platform compatibility explained
- **[Alternative Platforms](DEPLOYMENT.md)** - Render, Railway, Heroku, Docker

## 📸 Screenshots

![Dashboard Preview](https://via.placeholder.com/800x400?text=Add+Your+Dashboard+Screenshot)

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- Data provided by [CoinGecko API](https://www.coingecko.com/en/api)
- Built with [Streamlit](https://streamlit.io/)
- Charts powered by [Plotly](https://plotly.com/)

## 📧 Contact

Your Name - [@yourlinkedin](https://linkedin.com/in/yourprofile)

Project Link: [https://github.com/yourusername/crypto-analytics](https://github.com/yourusername/crypto-analytics)

---

⭐ Star this repo if you find it helpful!

## API Endpoints

```
GET  /health                       → Health check
GET  /api/v1/prices                → Latest snapshot (all coins)
GET  /api/v1/gainers?limit=5       → Top gainers
GET  /api/v1/market-cap?limit=10   → Top by market cap
GET  /api/v1/volume                → Volume comparison
GET  /api/v1/volatility?limit=10   → Volatility ranking
GET  /api/v1/history/{coin_id}     → Price history
GET  /api/v1/anomalies             → Z-score anomaly detection
GET  /api/v1/kpis                  → All KPIs (dashboard data)
POST /api/v1/etl/trigger           → Manually trigger ETL run
```

## Module Design Decisions

| Decision | Rationale |
|---|---|
| SQLite fallback | Zero-dependency local dev experience |
| UPSERT on (coin_id, extracted_at) | Idempotent reruns; no duplicates |
| Raw JSON snapshots | Full audit trail; enables historical replay |
| APScheduler + circuit breaker | Prevents infinite failure loops |
| Z-score anomaly detection | Statistically principled; no hardcoded thresholds |
| Redis caching with 55s TTL | Avoid hammering DB between 60s dashboard refreshes |
| Pydantic validation | Catches API schema drift before data enters DB |
| Dataclass TransformedCoin | Type safety + easy dict conversion for tests |
