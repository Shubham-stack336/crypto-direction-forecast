"""Crypto Trend Predictor - Spatial Glassmorphism Streamlit Dashboard.

Educational ML platform predicting next-day crypto direction (UP / DOWN).
"""

import sys
from pathlib import Path
ROOT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from datetime import datetime, timezone
import streamlit as st
import pandas as pd
import numpy as np

from app.services.data_service import DataService
from app.services.feature_service import FeatureService
from app.services.model_service import ModelService

# Page Configuration
st.set_page_config(
    page_title="Crypto Trend Predictor • Spatial AI",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom Spatial Glassmorphic CSS
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&family=JetBrains+Mono:wght@500;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }
    
    /* Main Background with ambient gradients */
    .stApp {
        background: radial-gradient(circle at 50% 0%, #111827 0%, #07090e 75%);
        color: #f8fafc;
    }
    
    /* Frosted Glass Card Container */
    .glass-card {
        background: rgba(15, 23, 42, 0.65);
        backdrop-filter: blur(24px) saturate(190%);
        -webkit-backdrop-filter: blur(24px) saturate(190%);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 18px;
        padding: 24px;
        box-shadow: 0 20px 45px -10px rgba(0, 0, 0, 0.65), inset 0 1px 0 rgba(255, 255, 255, 0.1);
        margin-bottom: 24px;
    }
    
    /* Glowing Badges */
    .badge-up {
        background: rgba(16, 185, 129, 0.15);
        color: #34d399;
        border: 1px solid rgba(16, 185, 129, 0.4);
        padding: 6px 16px;
        border-radius: 999px;
        font-weight: 800;
        letter-spacing: 0.05em;
        box-shadow: 0 0 20px rgba(16, 185, 129, 0.35);
        display: inline-block;
    }
    
    .badge-down {
        background: rgba(244, 63, 94, 0.15);
        color: #fb7185;
        border: 1px solid rgba(244, 63, 94, 0.4);
        padding: 6px 16px;
        border-radius: 999px;
        font-weight: 800;
        letter-spacing: 0.05em;
        box-shadow: 0 0 20px rgba(244, 63, 94, 0.35);
        display: inline-block;
    }
    
    /* Disclaimer */
    .disclaimer-box {
        background: rgba(245, 158, 11, 0.1);
        border: 1px solid rgba(245, 158, 11, 0.3);
        border-radius: 12px;
        padding: 14px 18px;
        color: #fde68a;
        font-size: 0.88rem;
        margin-bottom: 20px;
    }
    
    /* Metric Typography */
    .metric-value {
        font-family: 'JetBrains Mono', monospace;
        font-size: 2.2rem;
        font-weight: 800;
        background: linear-gradient(135deg, #ffffff 0%, #94a3b8 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# Header
st.markdown(
    """
    <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px;">
        <div>
            <div style="color: #38bdf8; font-size: 0.75rem; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase;">
                SPATIAL QUANT AI • DIRECTION PREDICTOR
            </div>
            <h1 style="margin: 4px 0 0; font-size: 2.4rem; font-weight: 800;">⚡ Crypto Trend Predictor</h1>
            <p style="color: #94a3b8; margin: 4px 0 0;">Next-day directional forecasting with zero lookahead leakage & honest baseline comparison.</p>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# Disclaimer Banner
st.markdown(
    """
    <div class="disclaimer-box">
        <strong>⚠️ Educational Project — Not Financial Advice:</strong>
        Cryptocurrency markets have high noise and regime shifts. Machine learning models offer statistical probabilistic estimates,
        not guarantees. Always compare models against a naive baseline.
    </div>
    """,
    unsafe_allow_html=True,
)

# Services
@st.cache_resource
def get_services():
    data_svc = DataService()
    feat_svc = FeatureService()
    model_svc = ModelService(data_service=data_svc, feature_service=feat_svc)
    return data_svc, feat_svc, model_svc

data_svc, feat_svc, model_svc = get_services()

# Sidebar Controls
with st.sidebar:
    st.markdown("### ⚙️ Model & Asset Config")
    symbol = st.selectbox(
        "Select Asset",
        ["BTC-USD", "ETH-USD", "SOL-USD", "DOGE-USD", "ADA-USD", "XRP-USD"],
        index=0,
    )
    train_ratio = st.slider("Chronological Train Split", min_value=0.6, max_value=0.85, value=0.8, step=0.05)
    force_retrain = st.button("🔄 Retrain Models Now", use_container_width=True)

# Data Ingestion & Features
with st.spinner("Fetching latest historical candles..."):
    df = data_svc.get_data(symbol)

# Model Training & Forecast
if force_retrain or not (model_svc.artifacts_dir / f"{symbol.lower().replace('-', '_')}_candidate.joblib").exists():
    with st.spinner(f"Training models for {symbol} with time-based split..."):
        summary = model_svc.train_and_compare_all(symbol, train_ratio=train_ratio)
else:
    # Quick load or run summary
    summary = model_svc.train_and_compare_all(symbol, train_ratio=train_ratio)

forecast = model_svc.predict_next_day(symbol)

# Layout Grid
col1, col2 = st.columns([1, 1.4])

with col1:
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    st.markdown("### 🎯 Tomorrow's Direction Forecast")
    
    dir_label = forecast["forecast_direction"]
    badge_class = "badge-up" if dir_label == "UP" else "badge-down"
    arrow = "▲" if dir_label == "UP" else "▼"
    
    st.markdown(
        f"""
        <div style="margin: 16px 0;">
            <span class="{badge_class}" style="font-size: 1.3rem;">{arrow} {dir_label}</span>
            <div style="color: #94a3b8; font-size: 0.88rem; margin-top: 8px;">Confidence: <strong>{forecast['confidence']*100:.1f}%</strong></div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    
    # Probability Bars
    st.markdown("#### Probability Breakdown")
    p_up = forecast["probabilities"]["UP"]
    p_down = forecast["probabilities"]["DOWN"]
    st.progress(p_up, text=f"UP Probability: {p_up*100:.1f}%")
    st.progress(p_down, text=f"DOWN Probability: {p_down*100:.1f}%")
    
    st.markdown(f"**Candidate Model Selected:** `{forecast['candidate_model'].replace('_', ' ').title()}`")
    st.info(forecast["honest_assessment"])
    st.markdown("</div>", unsafe_allow_html=True)

with col2:
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    st.markdown(f"### 📈 {symbol} Recent Price Trend")
    st.line_chart(df["close"].tail(60), color="#38bdf8", use_container_width=True)
    
    latest_meta = forecast["latest_candle"]
    m1, m2, m3 = st.columns(3)
    m1.metric("Last Close", f"${latest_meta['close']:,.2f}")
    m2.metric("14-Day RSI", f"{latest_meta['rsi_14']:.1f}")
    m3.metric("7-Day Volatility", f"{latest_meta['volatility_7d']*100:.2f}%")
    st.markdown("</div>", unsafe_allow_html=True)

# Model Comparison Leaderboard Table
st.markdown('<div class="glass-card">', unsafe_allow_html=True)
st.markdown("### 🏆 Model Comparison Leaderboard (Held-out Test Period)")
st.markdown(
    f"Tested on **{summary['test_samples']} days** ({summary['test_period'][0]} to {summary['test_period'][1]}) strictly after training data."
)

table_data = []
for model_name, metrics in summary["results"].items():
    table_data.append({
        "Model": model_name.replace("_", " ").title(),
        "Balanced Accuracy": f"{metrics['balanced_accuracy']*100:.2f}%",
        "Macro F1": f"{metrics['macro_f1']:.4f}",
        "Raw Accuracy": f"{metrics['accuracy']*100:.2f}%",
        "UP Hit Rate": f"{metrics['up_accuracy']*100:.2f}%",
        "DOWN Hit Rate": f"{metrics['down_accuracy']*100:.2f}%",
    })

comparison_df = pd.DataFrame(table_data)
st.dataframe(comparison_df, use_container_width=True, hide_index=True)

st.caption(
    "Note: Naive Baseline predicts the majority class observed in training. Balanced accuracy evaluates UP and DOWN classes equally."
)
st.markdown("</div>", unsafe_allow_html=True)
