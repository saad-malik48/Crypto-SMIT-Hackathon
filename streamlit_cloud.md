# Deploy to Streamlit Cloud (Free Hosting)

## Quick Deploy Steps

1. **Push to GitHub**
   ```bash
   git init
   git add .
   git commit -m "Initial commit: CRYPTEX Analytics Platform"
   git branch -M main
   git remote add origin https://github.com/YOUR_USERNAME/crypto-analytics.git
   git push -u origin main
   ```

2. **Deploy on Streamlit Cloud**
   - Go to https://share.streamlit.io/
   - Sign in with GitHub
   - Click "New app"
   - Select your repository: `YOUR_USERNAME/crypto-analytics`
   - Main file path: `dashboard.py`
   - Click "Deploy"

3. **Configuration (Optional)**
   - In Streamlit Cloud dashboard, go to "Settings" → "Secrets"
   - Add any environment variables if needed (the app works with SQLite by default)

## Your App Will Be Live At:
`https://YOUR_USERNAME-crypto-analytics.streamlit.app`

## Features Available:
✅ Free hosting
✅ Auto-deploys on git push
✅ HTTPS enabled
✅ Custom domain support (paid)
✅ SQLite database (built-in)
✅ Automatic restarts

## Note:
- Streamlit Cloud uses SQLite by default (no PostgreSQL setup needed)
- The ETL pipeline will run when the app starts
- Data refreshes every time the app restarts or when you trigger manual refresh
- Free tier: 1GB RAM, 1 CPU core, sufficient for this dashboard

## Alternative: Run ETL Separately
If you want continuous data updates, you can:
1. Deploy dashboard on Streamlit Cloud
2. Run ETL pipeline on a separate server (Heroku, Railway, etc.)
3. Use a shared PostgreSQL database (ElephantSQL, Supabase, etc.)
