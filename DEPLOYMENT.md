# Deployment Guide

## 🚀 Quick Deploy Options

### Option 1: Streamlit Cloud (Recommended - FREE)
Perfect for sharing the dashboard publicly.

**Steps:**
1. Push code to GitHub
2. Go to https://share.streamlit.io/
3. Connect your repo and deploy `dashboard.py`
4. Share the public URL!

**Live in 2 minutes** ✨

See [streamlit_cloud.md](streamlit_cloud.md) for detailed instructions.

---

### Option 2: Docker Compose (Full Stack)
Run everything locally with PostgreSQL + Redis.

```bash
docker-compose up -d
```

Access:
- Dashboard: http://localhost:8501
- API: http://localhost:8000/docs

---

### Option 3: Heroku (Dashboard + ETL)

**1. Install Heroku CLI**
```bash
# Windows
choco install heroku-cli

# Mac
brew tap heroku/brew && brew install heroku

# Linux
curl https://cli-assets.heroku.com/install.sh | sh
```

**2. Deploy**
```bash
heroku login
heroku create your-crypto-dashboard
git push heroku main
heroku open
```

**3. Add Procfile** (already included)
```
web: streamlit run dashboard.py --server.port=$PORT --server.address=0.0.0.0
worker: python etl_pipeline.py
```

---

### Option 4: Railway.app (Modern Alternative)

1. Go to https://railway.app/
2. Click "New Project" → "Deploy from GitHub"
3. Select your repo
4. Railway auto-detects Python and deploys
5. Add environment variables if needed

**Free tier:** 500 hours/month, $5 credit

---

### Option 5: Render.com (Free Tier)

1. Go to https://render.com/
2. New → Web Service
3. Connect GitHub repo
4. Build Command: `pip install -r requirements.txt`
5. Start Command: `streamlit run dashboard.py --server.port=$PORT --server.address=0.0.0.0`

---

### Option 6: Local Development

**Quick Start (SQLite):**
```bash
# Install dependencies
pip install -r requirements.txt

# Run ETL once
python etl_pipeline.py --once

# Launch dashboard
streamlit run dashboard.py
```

**With PostgreSQL:**
```bash
# Set environment variables
export DB_HOST=localhost
export DB_PORT=5432
export DB_NAME=crypto_analytics
export DB_USER=postgres
export DB_PASSWORD=yourpassword

# Initialize database
python database.py

# Run ETL continuously
python etl_pipeline.py

# In another terminal, launch dashboard
streamlit run dashboard.py
```

---

## 🌐 Sharing Your Project

### For LinkedIn Post:
```
🚀 Excited to share my latest project: CRYPTEX - Real-Time Crypto Analytics Platform!

✨ Features:
• Live crypto market data from CoinGecko API
• ETL pipeline with PostgreSQL/SQLite
• Interactive Streamlit dashboard with Plotly charts
• Anomaly detection using Z-score analysis
• FastAPI REST endpoints
• Docker containerization

🔗 Live Demo: [your-streamlit-url]
💻 GitHub: [your-github-url]

Built with: Python • Streamlit • PostgreSQL • Redis • Docker

#Python #DataEngineering #ETL #Streamlit #CryptoAnalytics #DataScience
```

### For GitHub README:
Add badges at the top:
```markdown
[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](your-app-url)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
```

---

## 📊 Database Options for Production

### Free PostgreSQL Hosting:
1. **Supabase** - https://supabase.com/ (500MB free)
2. **ElephantSQL** - https://www.elephantsql.com/ (20MB free)
3. **Neon** - https://neon.tech/ (3GB free)
4. **Railway** - https://railway.app/ (PostgreSQL included)

### Free Redis Hosting:
1. **Redis Cloud** - https://redis.com/try-free/ (30MB free)
2. **Upstash** - https://upstash.com/ (10K commands/day free)

---

## 🔒 Security Best Practices

1. **Never commit secrets**
   - Use `.env` files (already in `.gitignore`)
   - Use platform secret managers (Streamlit Secrets, Heroku Config Vars)

2. **API Rate Limits**
   - CoinGecko free tier: 10-50 calls/minute
   - Consider caching with Redis
   - Add exponential backoff (already implemented)

3. **Database Security**
   - Use strong passwords
   - Enable SSL for production databases
   - Restrict network access

---

## 📈 Monitoring & Logs

**Streamlit Cloud:**
- View logs in dashboard → "Manage app" → "Logs"

**Heroku:**
```bash
heroku logs --tail
```

**Docker:**
```bash
docker-compose logs -f etl
docker-compose logs -f dashboard
```

---

## 🆘 Troubleshooting

**Dashboard not loading data?**
```bash
# Run ETL manually first
python etl_pipeline.py --once
```

**PostgreSQL connection failed?**
- App automatically falls back to SQLite
- Check DB credentials in environment variables

**CoinGecko API rate limit?**
- Increase `ETL_INTERVAL_MINUTES` to 10 or 15
- Consider upgrading to CoinGecko Pro

**Port already in use?**
```bash
# Change Streamlit port
streamlit run dashboard.py --server.port=8502
```

---

## 💡 Next Steps

1. ⭐ Star the repo on GitHub
2. 📝 Customize the dashboard for your needs
3. 🔗 Share your deployment URL
4. 🤝 Contribute improvements via Pull Requests
5. 📱 Add mobile-responsive design
6. 🔔 Implement email/SMS alerts for anomalies
7. 📊 Add more analytics (RSI, MACD, etc.)

---

**Questions?** Open an issue on GitHub or reach out on LinkedIn!
