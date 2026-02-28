"""CRYPTEX Charts Page - Interactive visualizations and analytics"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timezone

st.set_page_config(
    page_title="CRYPTEX - Charts",
    page_icon="📈",
    layout="wide",
)

from analysis import (
    get_market_df, volume_comparison, volatility_ranking,
    price_history, detect_anomalies
)
from config import ZSCORE_THRESHOLD

# Custom CSS
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;700;800&family=JetBrains+Mono:wght@300;400;500&display=swap');
html, body, [class*="css"] { font-family: 'Syne', sans-serif !important; }
.main .block-container { padding-top: 1.5rem; }
</style>
""", unsafe_allow_html=True)

# Header
st.title("📈 Interactive Charts")
st.markdown("Explore detailed market visualizations and trends")

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
def load_volume():
    return volume_comparison()

@st.cache_data(ttl=55)
def load_volatility():
    return volatility_ranking(15)

@st.cache_data(ttl=55)
def load_anomalies():
    return detect_anomalies()

@st.cache_data(ttl=55)
def load_history(coin_id: str):
    return price_history(coin_id, 100)

market_df = load_market_df()
vol_data = load_volume()
volatility_data = load_volatility()
anomalies = load_anomalies()

# Sidebar Filters
with st.sidebar:
    st.markdown("### 🎛️ Chart Controls")
    
    top_n = st.slider("Number of coins to display", 5, 20, 10)
    
    chart_type = st.selectbox(
        "Chart Type",
        ["Bar Chart", "Line Chart", "Area Chart"]
    )
    
    st.markdown("---")
    st.markdown("### 📊 Anomaly Detection")
    z_threshold = st.slider(
        "Z-score threshold",
        1.0, 5.0, ZSCORE_THRESHOLD, 0.1
    )

# Anomaly Alert
if anomalies:
    st.warning(f"⚠️ **{len(anomalies)} Anomalies Detected** | Z-score ≥ {z_threshold}")
    
    cols = st.columns(len(anomalies[:3]))
    for idx, a in enumerate(anomalies[:3]):
        with cols[idx]:
            st.metric(
                a['symbol'].upper(),
                f"Z-score: {a['z_score']:+.2f}",
                f"{a['anomaly_type']}"
            )

st.markdown("---")

# Market Cap Chart
st.markdown("### 💰 Market Capitalization")

if not market_df.empty:
    df_top = market_df.nlargest(top_n, "market_cap")[["symbol","market_cap"]].copy()
    df_top["market_cap_B"] = df_top["market_cap"] / 1e9
    
    fig = go.Figure()
    
    if chart_type == "Bar Chart":
        fig.add_trace(go.Bar(
            x=df_top["symbol"],
            y=df_top["market_cap_B"],
            marker_color='#00f5c4',
            marker_line_width=0,
        ))
    elif chart_type == "Line Chart":
        fig.add_trace(go.Scatter(
            x=df_top["symbol"],
            y=df_top["market_cap_B"],
            mode='lines+markers',
            line=dict(color='#00f5c4', width=3),
            marker=dict(size=8)
        ))
    else:  # Area Chart
        fig.add_trace(go.Scatter(
            x=df_top["symbol"],
            y=df_top["market_cap_B"],
            fill='tozeroy',
            fillcolor='rgba(0,245,196,0.2)',
            line=dict(color='#00f5c4', width=2)
        ))
    
    fig.update_layout(
        title=f"Top {top_n} Cryptocurrencies by Market Cap (USD Billions)",
        xaxis_title="Cryptocurrency",
        yaxis_title="Market Cap (Billions USD)",
        template="plotly_dark",
        height=400
    )
    
    st.plotly_chart(fig, use_container_width=True)

# Price Change Chart
st.markdown("### 📊 24H Price Changes")

if not market_df.empty:
    df_change = market_df.nlargest(top_n, "price_change_24h")[["symbol","price_change_24h"]].copy()
    
    colors = ['#00f5c4' if x >= 0 else '#ff4b6e' for x in df_change["price_change_24h"]]
    
    fig2 = go.Figure(go.Bar(
        x=df_change["symbol"],
        y=df_change["price_change_24h"],
        marker_color=colors,
        marker_line_width=0,
    ))
    
    fig2.add_hline(y=0, line_color="rgba(255,255,255,0.2)", line_width=1)
    
    fig2.update_layout(
        title=f"Top {top_n} Price Changes (24H %)",
        xaxis_title="Cryptocurrency",
        yaxis_title="Price Change (%)",
        template="plotly_dark",
        height=400
    )
    
    st.plotly_chart(fig2, use_container_width=True)

# Volume & Volatility
col1, col2 = st.columns(2)

with col1:
    st.markdown("### 📦 Trading Volume")
    
    if vol_data:
        df_vol = pd.DataFrame(vol_data[:top_n])
        df_vol["volume_B"] = df_vol["total_volume"] / 1e9
        
        fig3 = go.Figure(go.Bar(
            x=df_vol["symbol"],
            y=df_vol["volume_B"],
            marker=dict(
                color=df_vol["volume_B"],
                colorscale='Viridis',
                showscale=False,
            ),
        ))
        
        fig3.update_layout(
            title="24H Trading Volume (USD Billions)",
            template="plotly_dark",
            height=350
        )
        
        st.plotly_chart(fig3, use_container_width=True)

with col2:
    st.markdown("### 🌊 Volatility Ranking")
    
    if volatility_data:
        df_vr = pd.DataFrame(volatility_data[:top_n])
        df_vr["vs_B"] = df_vr["volatility_score"] / 1e9
        
        fig4 = go.Figure(go.Bar(
            x=df_vr["symbol"],
            y=df_vr["vs_B"],
            marker=dict(
                color=df_vr["vs_B"],
                colorscale='Reds',
                showscale=False,
            ),
        ))
        
        fig4.update_layout(
            title="Volatility Score (|Δ%| × Volume)",
            template="plotly_dark",
            height=350
        )
        
        st.plotly_chart(fig4, use_container_width=True)

# Price History
st.markdown("### 📉 Price History")

if not market_df.empty and "coin_id" in market_df.columns:
    coin_options = market_df.sort_values("market_cap_rank")["coin_id"].tolist()
else:
    coin_options = ["bitcoin", "ethereum", "binancecoin"]

selected_coin = st.selectbox("Select Cryptocurrency", coin_options, index=0)
hist = load_history(selected_coin)

if hist:
    df_hist = pd.DataFrame(hist)
    if "extracted_at" in df_hist.columns:
        df_hist["extracted_at"] = pd.to_datetime(df_hist["extracted_at"])
        df_hist = df_hist.sort_values("extracted_at")
    
    fig_hist = go.Figure()
    fig_hist.add_trace(go.Scatter(
        x=df_hist["extracted_at"],
        y=df_hist["current_price"],
        mode="lines",
        line=dict(color='#00f5c4', width=2),
        fill="tozeroy",
        fillcolor="rgba(0,245,196,0.1)",
        name="Price",
    ))
    
    fig_hist.update_layout(
        title=f"{selected_coin.upper()} — Price History",
        xaxis_title="Time",
        yaxis_title="Price (USD)",
        template="plotly_dark",
        height=400
    )
    
    st.plotly_chart(fig_hist, use_container_width=True)
else:
    st.info(f"No history available for '{selected_coin}' yet")

# Footer
st.markdown("---")
st.markdown(
    f"<div style='text-align:center;font-family:monospace;font-size:10px;color:#8b949e'>"
    f"Last updated: {datetime.now(tz=timezone.utc).strftime('%H:%M:%S UTC')}"
    f"</div>",
    unsafe_allow_html=True
)
