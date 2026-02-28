"""
Home.py — CRYPTEX Home Page
Main landing page with overview and search functionality
"""

import streamlit as st
import pandas as pd
from datetime import datetime, timezone

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="CRYPTEX - Home",
    page_icon="₿",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Auto-run ETL on first load ───────────────────────────────────────────────
@st.cache_resource
def initialize_data():
    """Run ETL pipeline once on app startup if no data exists"""
    try:
        from load import get_row_count
        row_count = get_row_count()
        if row_count == 0:
            st.info("🔄 First time setup: Fetching crypto data from CoinGecko API...")
            from etl_pipeline import run_etl_once
            success = run_etl_once()
            if success:
                st.success("✅ Data loaded successfully!")
            else:
                st.warning("⚠️ ETL failed, but app will continue")
    except Exception as e:
        pass

initialize_data()

from analysis import kpi_summary, get_market_df, top_gainers
from load import get_row_count

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;700;800&family=JetBrains+Mono:wght@300;400;500&display=swap');

html, body, [class*="css"] {
    font-family: 'Syne', sans-serif !important;
    background: #080b10;
    color: #e8eaf0;
}
.main .block-container { padding-top: 1.5rem; }
.hero-section {
    text-align: center;
    padding: 3rem 0;
    background: linear-gradient(135deg, #0d1117, #161b22);
    border-radius: 20px;
    margin-bottom: 2rem;
    border: 1px solid rgba(0,245,196,0.12);
}
.hero-title {
    font-size: 3.5rem;
    font-weight: 800;
    background: linear-gradient(135deg, #00f5c4, #5ea7f5);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    margin-bottom: 1rem;
}
.hero-subtitle {
    font-size: 1.2rem;
    color: #8b949e;
    font-family: 'JetBrains Mono', monospace;
}
.kpi-card {
    background: linear-gradient(135deg, #0d1117, #161b22);
    border: 1px solid rgba(0,245,196,0.12);
    border-radius: 16px;
    padding: 20px 24px;
    text-align: center;
    transition: border-color 0.3s;
}
.kpi-card:hover { border-color: rgba(0,245,196,0.35); }
.kpi-label {
    font-size: 10px; letter-spacing: 2px;
    color: #56637a; text-transform: uppercase;
    font-family: 'JetBrains Mono', monospace;
}
.kpi-value {
    font-family: 'JetBrains Mono', monospace;
    font-size: 26px; font-weight: 500;
    color: #00f5c4; margin: 6px 0 2px;
}
.search-box {
    background: #161b22;
    border: 1px solid rgba(0,245,196,0.2);
    border-radius: 12px;
    padding: 12px 20px;
    color: #e8eaf0;
    font-family: 'JetBrains Mono', monospace;
    width: 100%;
    font-size: 14px;
}
.live-badge {
    display: inline-block;
    background: rgba(0,245,196,0.1);
    border: 1px solid rgba(0,245,196,0.25);
    border-radius: 20px;
    padding: 4px 16px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 11px;
    color: #00f5c4;
    letter-spacing: 2px;
}
</style>
""", unsafe_allow_html=True)

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="hero-section">
    <div class="hero-title">₿ CRYPTEX</div>
    <div class="hero-subtitle">Real-Time Cryptocurrency Analytics Platform</div>
    <br>
    <span class="live-badge">● LIVE</span>
</div>
""", unsafe_allow_html=True)

# ── Navigation Buttons ────────────────────────────────────────────────────────
col1, col2, col3 = st.columns(3)
with col1:
    st.page_link("Home.py", label="🏠 Home", use_container_width=True)
with col2:
    st.page_link("pages/1_📈_Charts.py", label="📈 Charts", use_container_width=True)
with col3:
    st.page_link("pages/2_💹_Market.py", label="💹 Market", use_container_width=True)

st.markdown("---")

# ── Search Bar ────────────────────────────────────────────────────────────────
st.markdown("### 🔍 Search Cryptocurrency")
search_query = st.text_input(
    "Search by name or symbol",
    placeholder="e.g., Bitcoin, BTC, Ethereum...",
    label_visibility="collapsed"
)

# ── Load data ─────────────────────────────────────────────────────────────────
@st.cache_data(ttl=55)
def load_kpis():
    return kpi_summary()

@st.cache_data(ttl=55)
def load_market_df():
    try:
        return get_market_df()
    except Exception:
        return pd.DataFrame()

@st.cache_data(ttl=55)
def load_gainers():
    return top_gainers(10)

kpis = load_kpis()
market_df = load_market_df()
gainers = load_gainers()

# ── Search Results ────────────────────────────────────────────────────────────
if search_query and not market_df.empty:
    filtered_df = market_df[
        market_df['name'].str.contains(search_query, case=False, na=False) |
        market_df['symbol'].str.contains(search_query, case=False, na=False)
    ]
    
    if not filtered_df.empty:
        st.markdown(f"### 📊 Search Results ({len(filtered_df)} found)")
        
        for _, coin in filtered_df.iterrows():
            col1, col2, col3, col4 = st.columns([2, 2, 2, 2])
            
            with col1:
                st.markdown(f"**{coin['name']}** ({coin['symbol'].upper()})")
            with col2:
                st.metric("Price", f"${coin['current_price']:,.2f}")
            with col3:
                change = coin['price_change_24h']
                st.metric("24h Change", f"{change:+.2f}%", delta=f"{change:.2f}%")
            with col4:
                st.metric("Market Cap", f"${coin['market_cap']/1e9:.2f}B")
            
            st.markdown("---")
    else:
        st.info(f"No results found for '{search_query}'")

# ── KPI Cards ─────────────────────────────────────────────────────────────────
st.markdown("### 📊 Market Overview")

k1, k2, k3, k4 = st.columns(4)

total_mcap = kpis.get("total_market_cap", 0)
avg_price = kpis.get("avg_price_top10", 0)
g = kpis.get("highest_gainer", {})
v = kpis.get("most_volatile", {})

with k1:
    st.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-label">Total Market Cap</div>
        <div class="kpi-value">${total_mcap/1e12:.2f}T</div>
    </div>""", unsafe_allow_html=True)

with k2:
    gain_pct = g.get("price_change_24h", 0)
    gain_sym = g.get("symbol", "—")
    st.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-label">Top Gainer 24H</div>
        <div class="kpi-value">{gain_sym} {gain_pct:+.2f}%</div>
    </div>""", unsafe_allow_html=True)

with k3:
    vol_sym = v.get("symbol", "—")
    st.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-label">Most Volatile</div>
        <div class="kpi-value">{vol_sym}</div>
    </div>""", unsafe_allow_html=True)

with k4:
    row_count = get_row_count()
    st.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-label">Total Records</div>
        <div class="kpi-value">{row_count:,}</div>
    </div>""", unsafe_allow_html=True)

st.markdown("")

# ── Top Gainers ───────────────────────────────────────────────────────────────
st.markdown("### 🚀 Top Gainers (24H)")

if gainers:
    cols = st.columns(5)
    for idx, coin in enumerate(gainers[:5]):
        with cols[idx]:
            st.metric(
                coin['symbol'].upper(),
                f"${coin['current_price']:,.2f}",
                f"{coin['price_change_24h']:+.2f}%"
            )

# ── Quick Stats ───────────────────────────────────────────────────────────────
st.markdown("### 📈 Quick Stats")

col1, col2 = st.columns(2)

with col1:
    if not market_df.empty:
        st.markdown("**Top 5 by Market Cap**")
        top5 = market_df.nlargest(5, 'market_cap')[['name', 'symbol', 'market_cap']]
        for _, row in top5.iterrows():
            st.write(f"• **{row['name']}** ({row['symbol'].upper()}) - ${row['market_cap']/1e9:.2f}B")

with col2:
    if not market_df.empty:
        st.markdown("**Top 5 by Volume**")
        top5_vol = market_df.nlargest(5, 'total_volume')[['name', 'symbol', 'total_volume']]
        for _, row in top5_vol.iterrows():
            st.write(f"• **{row['name']}** ({row['symbol'].upper()}) - ${row['total_volume']/1e9:.2f}B")

# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown(
    f"<div style='text-align:center;font-family:monospace;font-size:10px;color:#8b949e'>"
    f"Last updated: {datetime.now(tz=timezone.utc).strftime('%H:%M:%S UTC')} • "
    f"Data from CoinGecko API • Built with Streamlit"
    f"</div>",
    unsafe_allow_html=True
)
