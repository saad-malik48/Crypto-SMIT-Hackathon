"""CRYPTEX Market Page - Full market data with filtering and export"""

import streamlit as st
import pandas as pd
from datetime import datetime, timezone

st.set_page_config(
    page_title="CRYPTEX - Market",
    page_icon="💹",
    layout="wide",
)

from analysis import get_market_df, detect_anomalies
from load import get_row_count

# Custom CSS
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;700;800&family=JetBrains+Mono:wght@300;400;500&display=swap');
html, body, [class*="css"] { font-family: 'Syne', sans-serif !important; }
.main .block-container { padding-top: 1.5rem; }
</style>
""", unsafe_allow_html=True)

# Header
st.title("💹 Market Data")
st.markdown("Complete cryptocurrency market overview")

# ── Navigation Buttons ────────────────────────────────────────────────────────
col1, col2, col3 = st.columns(3)
with col1:
    st.page_link("Home.py", label="🏠 Home", use_container_width=True)
with col2:
    st.page_link("pages/1_📈_Charts.py", label="📈 Charts", use_container_width=True)
with col3:
    st.page_link("pages/2_💹_Market.py", label="💹 Market", use_container_width=True)

st.markdown("---")

# Load data with caching
@st.cache_data(ttl=55)
def load_market_df():
    try:
        return get_market_df()
    except Exception:
        return pd.DataFrame()

@st.cache_data(ttl=55)
def load_anomalies():
    return detect_anomalies()

market_df = load_market_df()
anomalies = load_anomalies()

# Sidebar Filters
with st.sidebar:
    st.markdown("### 🔍 Filters")
    
    # Search
    search = st.text_input("Search coin", placeholder="Bitcoin, BTC...")
    
    # Price range
    if not market_df.empty:
        min_price = float(market_df['current_price'].min())
        max_price = float(market_df['current_price'].max())
        
        price_range = st.slider(
            "Price Range (USD)",
            min_price, max_price,
            (min_price, max_price)
        )
    
    # Change filter
    change_filter = st.selectbox(
        "24H Change",
        ["All", "Gainers Only", "Losers Only"]
    )
    
    # Sort by
    sort_by = st.selectbox(
        "Sort By",
        ["Market Cap", "Price", "24H Change", "Volume", "Volatility"]
    )
    
    sort_order = st.radio("Order", ["Descending", "Ascending"])
    
    st.markdown("---")
    st.markdown(f"**Total Records:** {get_row_count():,}")

# Anomaly Alert
if anomalies:
    st.warning(f"⚠️ **{len(anomalies)} Anomalies Detected**")
    
    with st.expander("View Anomaly Details"):
        df_anom = pd.DataFrame(anomalies)
        st.dataframe(df_anom, use_container_width=True, hide_index=True)

st.markdown("---")

# Market Stats
if not market_df.empty:
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Coins", len(market_df))
    
    with col2:
        gainers = len(market_df[market_df['price_change_24h'] > 0])
        st.metric("Gainers (24H)", gainers, delta=f"{gainers/len(market_df)*100:.1f}%")
    
    with col3:
        losers = len(market_df[market_df['price_change_24h'] < 0])
        st.metric("Losers (24H)", losers, delta=f"-{losers/len(market_df)*100:.1f}%")
    
    with col4:
        avg_change = market_df['price_change_24h'].mean()
        st.metric("Avg Change", f"{avg_change:+.2f}%")

st.markdown("---")

# Filter Data
if not market_df.empty:
    filtered_df = market_df.copy()
    
    # Apply search filter
    if search:
        filtered_df = filtered_df[
            filtered_df['name'].str.contains(search, case=False, na=False) |
            filtered_df['symbol'].str.contains(search, case=False, na=False)
        ]
    
    # Apply price filter
    filtered_df = filtered_df[
        (filtered_df['current_price'] >= price_range[0]) &
        (filtered_df['current_price'] <= price_range[1])
    ]
    
    # Apply change filter
    if change_filter == "Gainers Only":
        filtered_df = filtered_df[filtered_df['price_change_24h'] > 0]
    elif change_filter == "Losers Only":
        filtered_df = filtered_df[filtered_df['price_change_24h'] < 0]
    
    # Apply sorting
    sort_col_map = {
        "Market Cap": "market_cap",
        "Price": "current_price",
        "24H Change": "price_change_24h",
        "Volume": "total_volume",
        "Volatility": "volatility_score"
    }
    
    sort_col = sort_col_map[sort_by]
    ascending = (sort_order == "Ascending")
    filtered_df = filtered_df.sort_values(sort_col, ascending=ascending)
    
    # Display Table
    st.markdown(f"### 📊 Market Table ({len(filtered_df)} coins)")
    
    # Format for display
    display_cols = [c for c in [
        "market_cap_rank", "symbol", "name", "current_price",
        "market_cap", "total_volume", "price_change_24h", "volatility_score"
    ] if c in filtered_df.columns]
    
    df_display = filtered_df[display_cols].copy()
    
    rename_map = {
        "market_cap_rank": "Rank",
        "symbol": "Symbol",
        "name": "Name",
        "current_price": "Price (USD)",
        "market_cap": "Market Cap",
        "total_volume": "Volume 24H",
        "price_change_24h": "Change 24H %",
        "volatility_score": "Volatility",
    }
    
    df_display = df_display.rename(columns=rename_map)
    
    # Format numbers
    if "Price (USD)" in df_display.columns:
        df_display["Price (USD)"] = df_display["Price (USD)"].apply(lambda x: f"${x:,.4f}")
    
    if "Market Cap" in df_display.columns:
        df_display["Market Cap"] = df_display["Market Cap"].apply(
            lambda x: f"${x/1e9:.2f}B" if x >= 1e9 else f"${x/1e6:.2f}M"
        )
    
    if "Volume 24H" in df_display.columns:
        df_display["Volume 24H"] = df_display["Volume 24H"].apply(
            lambda x: f"${x/1e9:.2f}B" if x >= 1e9 else f"${x/1e6:.2f}M"
        )
    
    if "Change 24H %" in df_display.columns:
        df_display["Change 24H %"] = df_display["Change 24H %"].apply(lambda x: f"{x:+.2f}%")
    
    if "Volatility" in df_display.columns:
        df_display["Volatility"] = df_display["Volatility"].apply(
            lambda x: f"{x/1e9:.2f}B" if x >= 1e9 else f"{x/1e6:.2f}M"
        )
    
    # Display with color coding
    st.dataframe(
        df_display,
        use_container_width=True,
        hide_index=True,
        height=600
    )
    
    # Export Options
    st.markdown("### 📥 Export Data")
    
    col1, col2 = st.columns(2)
    
    with col1:
        csv = filtered_df.to_csv(index=False)
        st.download_button(
            label="Download as CSV",
            data=csv,
            file_name=f"cryptex_market_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv"
        )
    
    with col2:
        json = filtered_df.to_json(orient='records', indent=2)
        st.download_button(
            label="Download as JSON",
            data=json,
            file_name=f"cryptex_market_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            mime="application/json"
        )

else:
    st.info("No market data available. Run the ETL pipeline first.")

# Footer
st.markdown("---")
st.markdown(
    f"<div style='text-align:center;font-family:monospace;font-size:10px;color:#8b949e'>"
    f"Last updated: {datetime.now(tz=timezone.utc).strftime('%H:%M:%S UTC')} • "
    f"Showing {len(filtered_df) if not market_df.empty else 0} of {len(market_df) if not market_df.empty else 0} coins"
    f"</div>",
    unsafe_allow_html=True
)
