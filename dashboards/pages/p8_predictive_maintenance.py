"""
Page 8 — Predictive Maintenance Intelligence
Purpose: ML model outputs — failure probabilities, risk scores, maintenance recommendations.
Audience: Reliability Engineer, Maintenance Superintendent, Operations Manager
"""

import sys
import math as _math
from pathlib import Path
import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from models.risk_scoring_engine import (
    score_all_assets, get_maintenance_recommendations,
    load_model_metadata, load_feature_importance
)
from dashboards.data_access import get_kpi_timeseries, get_failure_events
from dashboards.components.ui_components import (
    inject_css, page_header, section_header, alert_banner, apply_layout,
    THEME, RISK_COLORS
)
from config.settings import ASSET_REGISTRY


def render_predictive_maintenance():
    inject_css()
    page_header(
        "Predictive Maintenance Intelligence",
        "ML Failure Probability · 30-Day Risk Forecast · Maintenance Priority Ranking",
        "🤖"
    )

    scores   = score_all_assets()
    recs     = get_maintenance_recommendations()
    metadata = load_model_metadata()
    fi_df    = load_feature_importance()
    failures = get_failure_events()
    ts       = get_kpi_timeseries()

    # ── MODEL STATUS BANNER ───────────────────────────────────────────────
    if metadata:
        champion = metadata.get("champion_model", "Unknown")
        roc      = metadata.get("champion_test_roc_auc", 0)
        recall   = metadata.get("champion_recall", 0)
        f1       = metadata.get("champion_f1", 0)
        ts_date  = metadata.get("training_timestamp", "")[:10]

        st.markdown(f"""
        <div style="background:#0f2040;border:1px solid #00d4aa;border-left:4px solid #00d4aa;
                     border-radius:8px;padding:12px 20px;margin-bottom:16px;
                     display:flex;justify-content:space-between;flex-wrap:wrap;gap:12px;">
            <div>
                <div style="font-size:11px;color:#4d6a85;text-transform:uppercase;letter-spacing:0.1em;">ML Model Status</div>
                <div style="font-size:14px;font-weight:700;color:#00d4aa;margin-top:2px;">
                    ● {champion} — Calibrated Classifier · Trained {ts_date}
                </div>
            </div>
            <div style="display:flex;gap:30px;">
                <div style="text-align:center;">
                    <div style="font-size:10px;color:#4d6a85;text-transform:uppercase;">ROC-AUC</div>
                    <div style="font-size:20px;font-weight:700;color:#3b82f6;">{roc:.4f}</div>
                </div>
                <div style="text-align:center;">
                    <div style="font-size:10px;color:#4d6a85;text-transform:uppercase;">Recall</div>
                    <div style="font-size:20px;font-weight:700;color:#3b82f6;">{recall:.3f}</div>
                </div>
                <div style="text-align:center;">
                    <div style="font-size:10px;color:#4d6a85;text-transform:uppercase;">F1 Score</div>
                    <div style="font-size:20px;font-weight:700;color:#3b82f6;">{f1:.3f}</div>
                </div>
                <div style="text-align:center;">
                    <div style="font-size:10px;color:#4d6a85;text-transform:uppercase;">Features</div>
                    <div style="font-size:20px;font-weight:700;color:#3b82f6;">{metadata.get('feature_count', 0)}</div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    # ── FAILURE PROBABILITY GAUGES — HTML SVG, no plotly_chart in loop ───
    section_header("Current Failure Probability — All Assets (30-Day Horizon)")

    prob_cards = []
    for _, row in scores.iterrows():
        prob     = float(row["failure_probability_30d"])
        risk     = row.get("risk_level_ml", "Low")
        color    = RISK_COLORS.get(risk, THEME["blue"])
        asset_id = row["asset_id"]
        pct      = prob * 100
        rad      = _math.radians(180 - (pct / 100) * 180)
        x_end    = 50 + 38 * _math.cos(rad)
        y_end    = 50 - 38 * _math.sin(rad)
        large    = 1 if pct > 100 else 0
        prob_cards.append(f"""
        <div style="text-align:center;padding:10px 6px;background:#0f2040;
                    border:1px solid #1e3a5f;border-radius:10px;">
            <svg viewBox="0 0 100 62" width="110" height="68">
                <path d="M 12,52 A 38,38 0 0,1 88,52" fill="none"
                      stroke="#1e3a5f" stroke-width="9" stroke-linecap="round"/>
                <path d="M 12,52 A 38,38 0 {large},1 {x_end:.1f},{y_end:.1f}"
                      fill="none" stroke="{color}" stroke-width="9" stroke-linecap="round"/>
                <text x="50" y="48" text-anchor="middle" font-size="14"
                      font-weight="700" fill="{color}" font-family="sans-serif">{pct:.0f}%</text>
                <text x="50" y="59" text-anchor="middle" font-size="7"
                      fill="#4d6a85" font-family="sans-serif">30-day</text>
            </svg>
            <div style="font-size:12px;font-weight:700;color:#e8edf5;">{asset_id}</div>
            <span style="font-size:10px;font-weight:600;padding:1px 7px;border-radius:3px;
                         color:{color};background:{color}22;border:1px solid {color}44;">{risk}</span>
        </div>""")

    st.markdown(
        '<div style="display:grid;grid-template-columns:repeat(6,1fr);gap:8px;margin-bottom:20px;">'
        + "".join(prob_cards) + "</div>",
        unsafe_allow_html=True
    )

    st.markdown("<br>", unsafe_allow_html=True)

    # ── FAILURE PROBABILITY TIME SERIES ───────────────────────────────────
    section_header("Failure Probability Trend — Full Year with Actual Failure Events")
    if not ts.empty:
        ts["summary_date"] = pd.to_datetime(ts["summary_date"])

        fig_prob = go.Figure()
        for asset_id in ASSET_REGISTRY.keys():
            asset_ts = ts[ts["asset_id"] == asset_id].sort_values("summary_date")
            if asset_ts.empty:
                continue
            color = THEME["asset_colors"].get(asset_id, THEME["blue"])
            fig_prob.add_trace(go.Scatter(
                x=asset_ts["summary_date"],
                y=asset_ts["failure_probability_30d"] * 100,
                mode="lines",
                name=asset_id,
                line=dict(color=color, width=1.8),
                hovertemplate=f"<b>{asset_id}</b><br>%{{x|%d %b}}<br>Prob: %{{y:.1f}}%<extra></extra>",
            ))

        if not failures.empty:
            failures["failure_date"] = pd.to_datetime(failures["failure_date"])
            for _, frow in failures.iterrows():
                fig_prob.add_vline(
                    x=frow["failure_date"],
                    line_dash="dot",
                    line_color=RISK_COLORS.get(frow.get("failure_severity", "Minor"), THEME["red"]),
                    line_width=1.2,
                    opacity=0.6,
                )

        for y_val, label, clr in [
            (65, "Critical 65%", THEME["red"]),
            (40, "High 40%", THEME["amber"]),
            (20, "Medium 20%", THEME["blue"]),
        ]:
            fig_prob.add_hline(
                y=y_val, line_dash="dash", line_color=clr,
                line_width=1, opacity=0.7,
                annotation_text=label,
                annotation_font=dict(size=8, color=clr)
            )

        fig_prob.add_hrect(y0=65, y1=100, fillcolor="rgba(248,81,73,0.05)", line_width=0)
        fig_prob.add_hrect(y0=40, y1=65,  fillcolor="rgba(210,153,34,0.04)", line_width=0)

        apply_layout(fig_prob, height=360)
        fig_prob.update_layout(
            yaxis=dict(title="30-Day Failure Probability (%)", range=[-2, 105]),
            legend=dict(orientation="h", y=1.08, x=0),
            margin=dict(l=55, r=80, t=40, b=50),
        )
        st.plotly_chart(fig_prob, use_container_width=True, key="p8_chart_prob_trend")
        st.caption(
            "Vertical dotted lines indicate actual failure events. "
            "Model scores spike prior to failures — demonstrating predictive lead time."
        )

    st.markdown("<br>", unsafe_allow_html=True)

    # ── MAINTENANCE RECOMMENDATIONS ────────────────────────────────────────
    section_header("Maintenance Recommendations — Priority Ranked")
    for rec in recs:
        risk  = rec["risk_level"]
        color = RISK_COLORS.get(risk, THEME["blue"])
        prob  = rec["failure_probability"] * 100
        cost  = rec["expected_cost_if_fail"]

        st.markdown(f"""
        <div style="background:#0f2040;border:1px solid {color}55;
                     border-left:4px solid {color};border-radius:8px;
                     padding:14px 18px;margin-bottom:10px;">
            <div style="display:flex;justify-content:space-between;flex-wrap:wrap;gap:8px;">
                <div>
                    <div style="font-size:14px;font-weight:700;color:#e8edf5;">
                        {rec['asset_id']} — {rec['asset_name']}
                        <span style="font-size:10px;margin-left:10px;padding:2px 8px;
                               border-radius:3px;font-weight:600;
                               color:{color};background:{color}22;border:1px solid {color}44;">
                            {risk} RISK
                        </span>
                    </div>
                    <div style="font-size:11px;color:#4d6a85;margin-top:3px;">
                        {rec['asset_type']} · {rec['criticality']} Criticality · Priority Score: {rec['priority_score']:.0f}
                    </div>
                </div>
                <div style="display:flex;gap:24px;align-items:center;">
                    <div style="text-align:center;">
                        <div style="font-size:9px;color:#4d6a85;text-transform:uppercase;">Fail Prob</div>
                        <div style="font-size:18px;font-weight:700;color:{color};">{prob:.0f}%</div>
                    </div>
                    <div style="text-align:center;">
                        <div style="font-size:9px;color:#4d6a85;text-transform:uppercase;">Urgency</div>
                        <div style="font-size:12px;font-weight:600;color:#e8edf5;">{rec['urgency_label']}</div>
                    </div>
                    <div style="text-align:center;">
                        <div style="font-size:9px;color:#4d6a85;text-transform:uppercase;">Cost if Fail</div>
                        <div style="font-size:14px;font-weight:700;color:#ef4444;">${cost:,.0f}</div>
                    </div>
                </div>
            </div>
            <div style="margin-top:10px;font-size:12px;color:#8aa3be;line-height:1.5;">
                📋 {rec['recommended_action']}
            </div>
            {f'<div style="margin-top:6px;font-size:10px;color:#4d6a85;">Key factors: {rec["contributing_factors"]}</div>' if rec.get("contributing_factors") else ""}
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── FEATURE IMPORTANCE + CONFUSION MATRIX ─────────────────────────────
    col_fi, col_cm = st.columns([1.3, 0.7])

    with col_fi:
        section_header("Model Feature Importance — Top 20 Predictive Signals")
        if not fi_df.empty:
            top20 = fi_df.head(20).sort_values("importance_pct", ascending=True)

            def feat_color(feat):
                if "vib" in feat:                        return THEME["red"]
                if "temp" in feat:                       return THEME["orange"]
                if "eff" in feat:                        return THEME["green"]
                if "failure" in feat or "severity" in feat: return THEME["purple"]
                if "pm" in feat or "maint" in feat:      return THEME["blue"]
                if "age" in feat or "hour" in feat:      return THEME["amber"]
                return THEME["cyan"]

            fig_fi = go.Figure(go.Bar(
                x=top20["importance_pct"],
                y=top20["feature"],
                orientation="h",
                marker_color=[feat_color(f) for f in top20["feature"]],
                text=[f"{v:.1f}%" for v in top20["importance_pct"]],
                textposition="outside",
                textfont=dict(size=9),
            ))
            apply_layout(fig_fi, height=420)
            fig_fi.update_layout(
                xaxis_title="Importance %",
                margin=dict(l=220, r=50, t=20, b=40),
                showlegend=False,
            )
            st.plotly_chart(fig_fi, use_container_width=True, key="p8_chart_feature_importance")

            st.markdown("""
            <div style="font-size:10px;color:#4d6a85;margin-top:-8px;display:flex;gap:16px;flex-wrap:wrap;">
                <span style="color:#ef4444;">■ Vibration</span>
                <span style="color:#f97316;">■ Temperature</span>
                <span style="color:#00d4aa;">■ Efficiency</span>
                <span style="color:#a78bfa;">■ Failure History</span>
                <span style="color:#3b82f6;">■ Maintenance</span>
                <span style="color:#f59e0b;">■ Asset Age/Hours</span>
            </div>
            """, unsafe_allow_html=True)

    with col_cm:
        section_header("Model Evaluation — Test Set")
        if metadata:
            cm_data = metadata.get("champion_confusion_matrix", [[0, 0], [0, 0]])
            cm_arr  = np.array(cm_data)
            tn, fp, fn, tp = cm_arr[0][0], cm_arr[0][1], cm_arr[1][0], cm_arr[1][1]

            fig_cm = go.Figure(go.Heatmap(
                z=[[tn, fp], [fn, tp]],
                x=["Predicted: No Fail", "Predicted: Fail"],
                y=["Actual: No Fail", "Actual: Fail"],
                text=[[f"TN\n{tn}", f"FP\n{fp}"], [f"FN\n{fn}", f"TP\n{tp}"]],
                texttemplate="%{text}",
                textfont=dict(size=16, color="white"),
                colorscale=[
                    [0.0, THEME["bg_elevated"]],
                    [0.5, "rgba(88,166,255,0.5)"],
                    [1.0, "rgba(63,185,80,0.8)"],
                ],
                showscale=False,
            ))
            apply_layout(fig_cm, height=220)
            fig_cm.update_layout(
                margin=dict(l=130, r=20, t=20, b=80),
                xaxis=dict(tickfont=dict(size=10)),
                yaxis=dict(tickfont=dict(size=10)),
            )
            st.plotly_chart(fig_cm, use_container_width=True, key="p8_chart_confusion_matrix")

            roc  = metadata.get("champion_test_roc_auc", 0)
            prec = metadata.get("champion_precision", 0)
            rec  = metadata.get("champion_recall", 0)
            f1   = metadata.get("champion_f1", 0)

            st.markdown(f"""
            <div style="background:#0f2040;border:1px solid #1e3a5f;border-radius:6px;padding:12px 16px;">
                <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;">
                    {"".join([
                        f'<div style="text-align:center;"><div style="font-size:9px;color:#4d6a85;text-transform:uppercase;">{k}</div>'
                        f'<div style="font-size:18px;font-weight:700;color:#3b82f6;">{v:.4f}</div></div>'
                        for k, v in [("ROC-AUC", roc), ("Precision", prec), ("Recall", rec), ("F1 Score", f1)]
                    ])}
                </div>
                <div style="margin-top:10px;font-size:10px;color:#4d6a85;line-height:1.6;">
                    Model: {metadata.get('champion_model', 'RF')} + Isotonic Calibration<br>
                    Train: Jan–Sep 2024 ({metadata.get('training_rows', 0):,} records)<br>
                    Test: Oct–Dec 2024 ({metadata.get('test_rows', 0):,} records)<br>
                    Decision threshold: {metadata.get('threshold', 0.4):.0%}
                </div>
            </div>
            """, unsafe_allow_html=True)