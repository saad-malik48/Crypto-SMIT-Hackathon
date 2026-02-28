"""
dashboard.py — Streamlit Live Analytics Dashboard
===================================================
Layout:
  ┌──────────────────────────────────────────────────────────┐
  │  CRYPTEX ANALYTICS · Live ETL Dashboard                  │
  ├───────┬──────────┬────────────────┬────────────────────── │
  │ Total │ Highest  │ Most Volatile  │ Avg Price             │
  │ MCap  │ Gainer   │ Coin           │ (Top 10)              │
  ├───────┴──────────┴────────────────┴────────────────────── │
  │ Market Cap Bar Chart      │ Price Change Line/Bar         │
  ├───────────────────────────┤                               │
  │ Volume Comparison         │ Volatility Ranking            │
  ├───────────────────────────┴────────────────────────────── │
  │ Price History (per-coin selector)                        │
  ├────────────────────────────────────────────────────────── │
  │ Full Market Table + Anomaly Alert Panel                  │
  └──────────────────────────────────────────────────────────┘

Auto-refreshes every 60 seconds via st.rerun().
"""

import time
import logging
from datetime import datetime, timezone

import streamlit as st

# ── Streamlit page config must be first ──────────────────────────────────────
st.set_page_config(
    page_title="CRYPTEX Analytics",
    page_icon="₿",
    layout="wide",
    initial_sidebar_state="expanded",
)

logger = logging.getLogger(__name__)

# ── Try imports ───────────────────────────────────────────────────────────────
try:
    import pandas as pd
    import plotly.express as px
    import plotly.graph_objects as go
    _PLOTLY = True
except ImportError:
    _PLOTLY = False
    st.error("Run: pip install plotly pandas streamlit")
    st.stop()

from analysis import (
    kpi_summary, top_gainers, top_market_cap,
    volume_comparison, volatility_ranking,
    detect_anomalies, price_history, get_market_df,
)
from load import get_row_count
from config import DASHBOARD_REFRESH_SECONDS, ZSCORE_THRESHOLD


# ══════════════════════════════════════════════════════════════════════════════
#  Theme constants
# ══════════════════════════════════════════════════════════════════════════════

C_BG         = "#0d1117"
C_CARD       = "#161b22"
C_ACCENT     = "#00f5c4"
C_RED        = "#ff4b6e"
C_GREEN      = "#00f5c4"
C_YELLOW     = "#f5c842"
C_TEXT       = "#e8eaf0"
C_MUTED      = "#8b949e"

PLOTLY_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor ="rgba(0,0,0,0)",
    font=dict(family="monospace", color=C_TEXT, size=11),
    margin=dict(l=10, r=10, t=32, b=10),
    showlegend=False,
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;700;800&family=JetBrains+Mono:wght@300;400;500&display=swap');

html, body, [class*="css"] {
    font-family: 'Syne', sans-serif !important;
    background: #080b10;
    color: #e8eaf0;
}
.main .block-container { padding-top: 1.5rem; padding-bottom: 1rem; max-width: 100%; }
.kpi-card {
    background: linear-gradient(135deg, #0d1117, #161b22);
    border: 1px solid rgba(0,245,196,0.12);
    border-radius: 16px;
    padding: 20px 24px;
    text-align: center;
    position: relative;
    overflow: hidden;
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
.kpi-sub { font-family: 'JetBrains Mono', monospace; font-size: 11px; color: #8b949e; }
.kpi-accent-red  .kpi-value { color: #ff4b6e !important; }
.kpi-accent-gold .kpi-value { color: #f5c842 !important; }
.kpi-accent-blue .kpi-value { color: #5ea7f5 !important; }
.section-title {
    font-size: 11px; letter-spacing: 3px; text-transform: uppercase;
    color: #56637a; font-family: 'JetBrains Mono', monospace;
    border-bottom: 1px solid rgba(255,255,255,0.06);
    padding-bottom: 8px; margin: 24px 0 16px;
}
.anomaly-alert {
    background: rgba(255,75,110,0.08);
    border: 1px solid rgba(255,75,110,0.25);
    border-radius: 12px;
    padding: 12px 16px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 12px;
    color: #ff4b6e;
}
.live-badge {
    display: inline-block;
    background: rgba(0,245,196,0.1);
    border: 1px solid rgba(0,245,196,0.25);
    border-radius: 20px;
    padding: 2px 12px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 10px;
    color: #00f5c4;
    letter-spacing: 2px;
}
div[data-testid="stDataFrame"] { border-radius: 12px; overflow: hidden; }
div[data-testid="metric-container"] { background: transparent; }
</style>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
#  Data loading (cached, refreshes every 55s)
# ══════════════════════════════════════════════════════════════════════════════

@st.cache_data(ttl=55)
def load_kpis() -> dict:
    return kpi_summary()

@st.cache_data(ttl=55)
def load_market_df() -> pd.DataFrame:
    try:
        return get_market_df()
    except Exception:
        return pd.DataFrame()

@st.cache_data(ttl=55)
def load_volume() -> list[dict]:
    return volume_comparison()

@st.cache_data(ttl=55)
def load_volatility() -> list[dict]:
    return volatility_ranking(10)

@st.cache_data(ttl=55)
def load_gainers() -> list[dict]:
    return top_gainers(10)

@st.cache_data(ttl=55)
def load_anomalies() -> list[dict]:
    return detect_anomalies()

@st.cache_data(ttl=55)
def load_history(coin_id: str) -> list[dict]:
    return price_history(coin_id, 100)

@st.cache_data(ttl=55)
def load_row_count() -> int:
    try:
        return get_row_count()
    except Exception:
        return 0


# ══════════════════════════════════════════════════════════════════════════════
#  Helpers
# ══════════════════════════════════════════════════════════════════════════════

def fmt_usd(v, decimals=2) -> str:
    v = float(v or 0)
    if v >= 1e12: return f"${v/1e12:.2f}T"
    if v >= 1e9:  return f"${v/1e9:.2f}B"
    if v >= 1e6:  return f"${v/1e6:.2f}M"
    if v >= 1e3:  return f"${v/1e3:.2f}K"
    return f"${v:.{decimals}f}"


def chg_color(v: float) -> str:
    return C_GREEN if v >= 0 else C_RED


def chg_arrow(v: float) -> str:
    return "▲" if v >= 0 else "▼"


def plotly_bar(df, x, y, title, color_col=None, color_pos=C_GREEN, color_neg=C_RED):
    if color_col:
        colors = [color_pos if v >= 0 else color_neg for v in df[color_col]]
    else:
        colors = C_ACCENT

    fig = go.Figure(go.Bar(
        x=df[x], y=df[y],
        marker_color=colors,
        marker_line_width=0,
        opacity=0.85,
    ))
    fig.update_layout(title=dict(text=title, font_size=12), **PLOTLY_LAYOUT)
    fig.update_xaxes(showgrid=False, tickfont_size=10)
    fig.update_yaxes(showgrid=True, gridcolor="rgba(255,255,255,0.05)", tickfont_size=10)
    return fig


# ══════════════════════════════════════════════════════════════════════════════
#  Sidebar
# ══════════════════════════════════════════════════════════════════════════════

with st.sidebar:
    st.markdown("## ₿ CRYPTEX")
    st.markdown('<span class="live-badge">● LIVE</span>', unsafe_allow_html=True)
    st.markdown("---")

    refresh_interval = st.slider(
        "Auto-refresh (seconds)", min_value=10, max_value=300,
        value=DASHBOARD_REFRESH_SECONDS, step=10
    )
    z_threshold = st.slider(
        "Anomaly Z-score threshold", min_value=1.0, max_value=5.0,
        value=ZSCORE_THRESHOLD, step=0.1
    )
    top_n = st.selectbox("Top N coins to display", [5, 10, 15, 20], index=1)

    st.markdown("---")
    st.markdown("**Pipeline Info**")
    row_count = load_row_count()
    st.metric("DB Records", f"{row_count:,}")
    st.metric("ETL Interval", "5 min")
    st.metric("Refresh", f"{refresh_interval}s")

    st.markdown("---")
    if st.button("🔄 Force Refresh", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    st.markdown("---")
    st.caption("Built with: Python · PostgreSQL · CoinGecko · Streamlit · Plotly")


# ══════════════════════════════════════════════════════════════════════════════
#  Main Dashboard
# ══════════════════════════════════════════════════════════════════════════════

# ── Header ───────────────────────────────────────────────────────────────────
col_title, col_ts = st.columns([3, 1])
with col_title:
    st.markdown("# CRYPTEX — Real-Time Crypto Analytics")
with col_ts:
    st.markdown(
        f"<div style='text-align:right;font-family:monospace;font-size:11px;"
        f"color:{C_MUTED};padding-top:20px'>"
        f"Last updated: {datetime.now(tz=timezone.utc).strftime('%H:%M:%S UTC')}</div>",
        unsafe_allow_html=True
    )

# ── Load data ─────────────────────────────────────────────────────────────────
kpis      = load_kpis()
market_df = load_market_df()
gainers   = load_gainers()
anomalies = load_anomalies()

# ── KPI Cards ────────────────────────────────────────────────────────────────
st.markdown('<div class="section-title">📊  KEY PERFORMANCE INDICATORS</div>', unsafe_allow_html=True)

k1, k2, k3, k4 = st.columns(4)

total_mcap = kpis.get("total_market_cap", 0)
avg_price  = kpis.get("avg_price_top10", 0)
g = kpis.get("highest_gainer", {})
v = kpis.get("most_volatile", {})

with k1:
    st.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-label">Total Market Cap</div>
        <div class="kpi-value">{fmt_usd(total_mcap)}</div>
        <div class="kpi-sub">All tracked coins</div>
    </div>""", unsafe_allow_html=True)

with k2:
    gain_pct = g.get("price_change_24h", 0)
    gain_sym = g.get("symbol", "—")
    color_cls = "kpi-accent-red" if gain_pct < 0 else ""
    st.markdown(f"""
    <div class="kpi-card {color_cls}">
        <div class="kpi-label">Highest 24H Gainer</div>
        <div class="kpi-value">{gain_sym} {chg_arrow(gain_pct)}{abs(gain_pct):.2f}%</div>
        <div class="kpi-sub">{g.get("name", "")} · ${g.get("current_price", 0):,.2f}</div>
    </div>""", unsafe_allow_html=True)

with k3:
    vol_sym   = v.get("symbol", "—")
    vol_score = v.get("volatility_score", 0)
    st.markdown(f"""
    <div class="kpi-card kpi-accent-gold">
        <div class="kpi-label">Most Volatile Coin</div>
        <div class="kpi-value">{vol_sym}</div>
        <div class="kpi-sub">Score: {fmt_usd(vol_score)}</div>
    </div>""", unsafe_allow_html=True)

with k4:
    st.markdown(f"""
    <div class="kpi-card kpi-accent-blue">
        <div class="kpi-label">Avg Price (Top 10)</div>
        <div class="kpi-value">{fmt_usd(avg_price)}</div>
        <div class="kpi-sub">Across top 10 by mcap</div>
    </div>""", unsafe_allow_html=True)


# ── Anomaly Alert ─────────────────────────────────────────────────────────────
if anomalies:
    st.markdown(f"""
    <div class="anomaly-alert">
        ⚠️  <b>ANOMALY DETECTED</b> — {len(anomalies)} coin(s) with |Z-score| ≥ {z_threshold}:
        {" · ".join([f"{a['symbol']} ({a['anomaly_type']}, z={a['z_score']:+.2f})" for a in anomalies])}
    </div>""", unsafe_allow_html=True)
    st.markdown("")


# ── Charts Row 1: Market Cap + Price Change ───────────────────────────────────
st.markdown('<div class="section-title">📈  MARKET OVERVIEW</div>', unsafe_allow_html=True)
ch1, ch2 = st.columns(2)

with ch1:
    if not market_df.empty:
        df_top = market_df.nlargest(top_n, "market_cap")[["symbol","market_cap"]].copy()
        df_top["market_cap_B"] = df_top["market_cap"] / 1e9
        fig = plotly_bar(df_top, "symbol", "market_cap_B", f"Market Cap — Top {top_n} (USD Billions)")
        fig.update_traces(marker_color=C_ACCENT)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No market data yet — run the ETL pipeline first.\n\n`python etl_pipeline.py --once`")

with ch2:
    df_gain = pd.DataFrame(gainers[:top_n]) if gainers else pd.DataFrame()
    if not df_gain.empty:
        fig = plotly_bar(
            df_gain, "symbol", "price_change_24h",
            f"24H Price Change % — Top {top_n}",
            color_col="price_change_24h",
        )
        fig.add_hline(y=0, line_color="rgba(255,255,255,0.15)", line_width=1)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Awaiting data...")


# ── Charts Row 2: Volume + Volatility ────────────────────────────────────────
st.markdown('<div class="section-title">📊  VOLUME & VOLATILITY</div>', unsafe_allow_html=True)
ch3, ch4 = st.columns(2)

with ch3:
    vol_data = load_volume()
    df_vol = pd.DataFrame(vol_data[:top_n]) if vol_data else pd.DataFrame()
    if not df_vol.empty:
        df_vol["volume_B"] = df_vol["total_volume"] / 1e9
        fig = go.Figure(go.Bar(
            x=df_vol["symbol"],
            y=df_vol["volume_B"],
            marker=dict(
                color=df_vol["volume_B"],
                colorscale=[[0,"#1a3a4f"],[0.5,"#00a8d6"],[1.0,C_ACCENT]],
                showscale=False,
            ),
        ))
        fig.update_layout(title="24H Volume (USD Billions)", **PLOTLY_LAYOUT)
        fig.update_xaxes(showgrid=False)
        fig.update_yaxes(showgrid=True, gridcolor="rgba(255,255,255,0.05)")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Awaiting data...")

with ch4:
    vr_data = load_volatility()
    df_vr = pd.DataFrame(vr_data[:top_n]) if vr_data else pd.DataFrame()
    if not df_vr.empty:
        df_vr["vs_B"] = df_vr["volatility_score"] / 1e9
        fig = go.Figure(go.Bar(
            x=df_vr["symbol"],
            y=df_vr["vs_B"],
            marker=dict(
                color=df_vr["vs_B"],
                colorscale=[[0,"#3a1a2f"],[0.5,"#c800a8"],[1.0,C_YELLOW]],
                showscale=False,
            ),
        ))
        fig.update_layout(title="Volatility Score Ranking (|Δ%| × Volume)", **PLOTLY_LAYOUT)
        fig.update_xaxes(showgrid=False)
        fig.update_yaxes(showgrid=True, gridcolor="rgba(255,255,255,0.05)")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Awaiting data...")


# ── Price History Chart ───────────────────────────────────────────────────────
st.markdown('<div class="section-title">📉  PRICE HISTORY</div>', unsafe_allow_html=True)

if not market_df.empty and "coin_id" in market_df.columns:
    coin_options = market_df.sort_values("market_cap_rank")["coin_id"].tolist()
else:
    coin_options = ["bitcoin", "ethereum", "binancecoin"]

selected_coin = st.selectbox("Select Coin", coin_options, index=0)
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
        line=dict(color=C_ACCENT, width=2),
        fill="tozeroy",
        fillcolor="rgba(0,245,196,0.06)",
        name="Price",
    ))
    fig_hist.update_layout(
        title=f"{selected_coin.upper()} — Price History",
        **PLOTLY_LAYOUT,
        height=280,
    )
    fig_hist.update_xaxes(showgrid=False, tickfont_size=9)
    fig_hist.update_yaxes(showgrid=True, gridcolor="rgba(255,255,255,0.05)", tickprefix="$")
    st.plotly_chart(fig_hist, use_container_width=True)
else:
    st.info(f"No history yet for '{selected_coin}' — ETL runs every 5 minutes")


# ── Full Market Table ─────────────────────────────────────────────────────────
st.markdown('<div class="section-title">🗂  FULL MARKET TABLE</div>', unsafe_allow_html=True)

if not market_df.empty:
    display_cols = [c for c in [
        "market_cap_rank","symbol","name","current_price",
        "market_cap","total_volume","price_change_24h","volatility_score"
    ] if c in market_df.columns]

    df_display = market_df[display_cols].copy()
    rename_map = {
        "market_cap_rank":  "Rank",
        "symbol":           "Symbol",
        "name":             "Name",
        "current_price":    "Price (USD)",
        "market_cap":       "Market Cap",
        "total_volume":     "Volume 24H",
        "price_change_24h": "Chg 24H %",
        "volatility_score": "Volatility Score",
    }
    df_display = df_display.rename(columns=rename_map)

    # Format for display
    if "Price (USD)" in df_display.columns:
        df_display["Price (USD)"] = df_display["Price (USD)"].apply(lambda x: f"${x:,.4f}")
    if "Market Cap" in df_display.columns:
        df_display["Market Cap"] = df_display["Market Cap"].apply(fmt_usd)
    if "Volume 24H" in df_display.columns:
        df_display["Volume 24H"] = df_display["Volume 24H"].apply(fmt_usd)
    if "Chg 24H %" in df_display.columns:
        df_display["Chg 24H %"] = df_display["Chg 24H %"].apply(lambda x: f"{x:+.2f}%")

    st.dataframe(df_display, use_container_width=True, hide_index=True, height=420)
else:
    st.info("Run `python etl_pipeline.py --once` to populate data.")


# ── Anomaly Detail Table ──────────────────────────────────────────────────────
if anomalies:
    st.markdown('<div class="section-title">⚠️  ANOMALY DETAIL</div>', unsafe_allow_html=True)
    df_anom = pd.DataFrame(anomalies)
    df_anom.columns = [c.replace("_"," ").title() for c in df_anom.columns]
    st.dataframe(df_anom, use_container_width=True, hide_index=True)


# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown(
    f"<div style='text-align:center;font-family:monospace;font-size:10px;color:{C_MUTED}'>"
    f"CRYPTEX Analytics Platform · ETL + PostgreSQL + CoinGecko + Streamlit · "
    f"Auto-refresh in {refresh_interval}s · {row_count:,} DB records"
    f"</div>",
    unsafe_allow_html=True
)


# ══════════════════════════════════════════════════════════════════════════════
#  Auto-refresh countdown
# ══════════════════════════════════════════════════════════════════════════════
placeholder = st.empty()
for remaining in range(refresh_interval, 0, -1):
    placeholder.markdown(
        f"<div style='text-align:center;font-family:monospace;font-size:10px;"
        f"color:{C_MUTED};padding:4px'>🔄 Refreshing in {remaining}s</div>",
        unsafe_allow_html=True
    )
    time.sleep(1)

placeholder.empty()
st.cache_data.clear()
st.rerun()
