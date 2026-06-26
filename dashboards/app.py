"""
ORPMI Platform — Main Application Entry Point
Works on: Local · Docker · Streamlit Cloud
Dark Navy Industrial Theme
"""

import sys
import os
import subprocess
from pathlib import Path

# ── Absolute path setup ───────────────────────────────────────────────────
_root = Path(__file__).resolve().parent.parent
for _p in [str(_root), "/app"]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

import streamlit as st

st.set_page_config(
    page_title="ORPMI | Operational Reliability Platform",
    page_icon="⚙️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Auto-setup ────────────────────────────────────────────────────────────
_db    = _root / "database" / "orpmi_dev.db"
_model = _root / "models" / "artifacts" / "champion_model.pkl"
_env   = {**os.environ, "PYTHONPATH": str(_root)}

def _run(script: Path, label: str):
    """Run a setup script. Shows error details if it fails."""
    result = subprocess.run(
        [sys.executable, str(script)],
        cwd=str(_root),
        env=_env,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        st.error(f"Setup failed — {label}")
        st.code(result.stderr[-2000:] if result.stderr else result.stdout[-2000:])
        st.stop()

if not _db.exists():
    with st.spinner("First run — initialising database (~60 seconds)..."):
        _run(_root / "scripts" / "setup_database.py", "database setup")
    st.rerun()

if not _model.exists():
    with st.spinner("Training ML model (~30 seconds)..."):
        _run(_root / "scripts" / "train_models.py", "model training")
    st.rerun()

# Auto-retrain if sklearn version changed
try:
    import pickle
    with open(_model, "rb") as _f:
        pickle.load(_f)
except Exception:
    with st.spinner("Updating ML model for current environment..."):
        _run(_root / "scripts" / "train_models.py", "model retraining")
    st.rerun()

# ── UI ────────────────────────────────────────────────────────────────────
from dashboards.components.ui_components import inject_css
inject_css()

with st.sidebar:
    st.markdown("""
    <div style="padding:12px 0 8px 0;">
        <div style="font-size:16px;font-weight:700;color:#e8edf5;letter-spacing:-0.3px;">
            ⚙️ ORPMI Platform
        </div>
        <div style="font-size:11px;color:#4d6a85;margin-top:3px;">
            Offshore Production Complex · OPC-Alpha
        </div>
    </div>
    """, unsafe_allow_html=True)
    st.markdown('<hr style="border-color:#1e3a5f;margin:6px 0 12px;">', unsafe_allow_html=True)

    page = st.radio(
        "nav",
        options=[
            "🏠  Operations Overview",
            "📊  Reliability Scorecard",
            "⏱️  Downtime Analysis",
            "🔧  Maintenance Performance",
            "⚡  Asset Health Monitor",
            "🌡️  Sensor Trends",
            "📋  Failure Analysis",
            "🤖  Predictive Maintenance",
            "🎯  Executive Intelligence",
            "➕  Data Entry",
        ],
        label_visibility="collapsed",
    )

    st.markdown('<hr style="border-color:#1e3a5f;margin:12px 0 10px;">', unsafe_allow_html=True)
    st.markdown("""
    <div style="font-size:10px;color:#4d6a85;line-height:2.1;">
        <div>📅 Data: Jan–Dec 2024</div>
        <div>🤖 ML: Random Forest · AUC 0.9381</div>
        <div>📐 ISO 14224 · ISO 10816</div>
        <div style="margin-top:6px;color:#00d4aa;font-weight:600;">● Platform Online</div>
    </div>
    """, unsafe_allow_html=True)

# ── Page routing ──────────────────────────────────────────────────────────
if "Operations Overview" in page:
    from dashboards.pages.p1_operations_overview import render_operations_overview
    render_operations_overview()
elif "Reliability Scorecard" in page:
    from dashboards.pages.p2_reliability_scorecard import render_reliability_scorecard
    render_reliability_scorecard()
elif "Downtime Analysis" in page:
    from dashboards.pages.p3_downtime_analysis import render_downtime_analysis
    render_downtime_analysis()
elif "Maintenance Performance" in page:
    from dashboards.pages.p4_maintenance_performance import render_maintenance_performance
    render_maintenance_performance()
elif "Asset Health Monitor" in page:
    from dashboards.pages.p5_asset_health import render_asset_health
    render_asset_health()
elif "Sensor Trends" in page:
    from dashboards.pages.p6_sensor_trends import render_sensor_trends
    render_sensor_trends()
elif "Failure Analysis" in page:
    from dashboards.pages.p7_failure_analysis import render_failure_analysis
    render_failure_analysis()
elif "Predictive Maintenance" in page:
    from dashboards.pages.p8_predictive_maintenance import render_predictive_maintenance
    render_predictive_maintenance()
elif "Executive Intelligence" in page:
    from dashboards.pages.p9_executive_intelligence import render_executive_intelligence
    render_executive_intelligence()
elif "Data Entry" in page:
    from dashboards.pages.p10_data_entry import render_data_entry
    render_data_entry()
