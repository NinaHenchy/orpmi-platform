"""
Page 5 — Asset Health Monitor
Purpose: Real-time asset health scoring, risk heatmap, maintenance priority matrix.
Audience: Reliability Engineer, Asset Integrity Manager, Maintenance Superintendent
"""

import sys
from pathlib import Path
import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from dashboards.data_access import get_latest_kpis, get_kpi_timeseries, get_inspection_records
from dashboards.components.ui_components import (
    inject_css, page_header, section_header, apply_layout, alert_banner, THEME, RISK_COLORS
)
from config.settings import ASSET_REGISTRY, KPI_THRESHOLDS


def render_asset_health():
    inject_css()
    page_header(
        "Asset Health Monitor",
        "Real-Time Health Scoring · Risk Classification · Maintenance Priority Matrix",
        "⚡"
    )

    kpis = get_latest_kpis()
    ts = get_kpi_timeseries()
    inspections = get_inspection_records()

    if kpis.empty:
        st.error("No data available.")
        return

    # ── CRITICAL ASSET ALERTS ─────────────────────────────────────────────
    critical_assets = kpis[kpis["risk_level"] == "Critical"]
    high_assets = kpis[kpis["risk_level"] == "High"]

    for _, row in critical_assets.iterrows():
        alert_banner(
            f"CRITICAL: {row['asset_id']} — {row['asset_name']} | "
            f"Health: {row['health_score']:.0f}/100 | "
            f"Fail Probability: {row['failure_probability_30d']*100:.0f}% | "
            f"Priority Score: {row['maintenance_priority_score']:.0f} — Immediate action required.",
            level="critical"
        )
    for _, row in high_assets.iterrows():
        alert_banner(
            f"HIGH RISK: {row['asset_id']} — {row['asset_name']} | "
            f"Health: {row['health_score']:.0f}/100 | "
            f"Fail Probability: {row['failure_probability_30d']*100:.0f}% — Schedule inspection within 14 days.",
            level="warning"
        )

    st.markdown("<br>", unsafe_allow_html=True)

    # ── HEALTH GAUGE CARDS ────────────────────────────────────────────────
    section_header("Asset Health Score — Current Status")

    import math as _math
    gauge_cards = []
    for _, row in kpis.iterrows():
        health     = float(row["health_score"])
        asset_id   = row["asset_id"]
        asset_name = row["asset_name"].split()[0]
        risk       = row["risk_level"]
        color      = THEME["green"] if health >= 80 else (THEME["amber"] if health >= 60 else THEME["red"])
        risk_color = RISK_COLORS.get(risk, THEME["blue"])
        rad        = _math.radians(180 - (health / 100) * 180)
        x_end      = 50 + 38 * _math.cos(rad)
        y_end      = 50 - 38 * _math.sin(rad)
        large      = 1 if (health / 100) * 180 > 180 else 0
        gauge_cards.append(f"""
        <div style="text-align:center;padding:10px 6px;background:#0f2040;
                    border:1px solid #1e3a5f;border-radius:10px;">
            <svg viewBox="0 0 100 62" width="110" height="68">
                <path d="M 12,52 A 38,38 0 0,1 88,52" fill="none"
                      stroke="#1e3a5f" stroke-width="9" stroke-linecap="round"/>
                <path d="M 12,52 A 38,38 0 {large},1 {x_end:.1f},{y_end:.1f}"
                      fill="none" stroke="{color}" stroke-width="9" stroke-linecap="round"/>
                <text x="50" y="50" text-anchor="middle" font-size="15"
                      font-weight="700" fill="{color}" font-family="sans-serif">{health:.0f}</text>
                <text x="50" y="60" text-anchor="middle" font-size="7"
                      fill="#4d6a85" font-family="sans-serif">/100</text>
            </svg>
            <div style="font-size:12px;font-weight:700;color:#e8edf5;">{asset_id}</div>
            <div style="font-size:10px;color:#4d6a85;margin-bottom:4px;">{asset_name}</div>
            <span style="font-size:10px;font-weight:600;padding:1px 7px;border-radius:3px;
                         color:{risk_color};background:{risk_color}22;
                         border:1px solid {risk_color}44;">{risk}</span>
        </div>""")
    st.markdown(
        '<div style="display:grid;grid-template-columns:repeat(6,1fr);gap:8px;margin-bottom:20px;">'
        + "".join(gauge_cards) + "</div>",
        unsafe_allow_html=True
    )
    st.markdown("<br>", unsafe_allow_html=True)

    # ── HEALTH TREND ──────────────────────────────────────────────────────
    section_header("Health Score Trend — All Assets (Last 90 Days)")
    if not ts.empty:
        # Last 90 days
        ts_sorted = ts.sort_values("summary_date")
        ts_recent = ts_sorted[ts_sorted["summary_date"] >= ts_sorted["summary_date"].max()]
        ts_90d = ts_sorted.groupby("asset_id").tail(90)

        fig_ht = go.Figure()
        for asset_id in kpis["asset_id"].tolist():
            asset_ts = ts_90d[ts_90d["asset_id"] == asset_id]
            if asset_ts.empty:
                continue
            color = THEME["asset_colors"].get(asset_id, THEME["blue"])
            fig_ht.add_trace(go.Scatter(
                x=asset_ts["summary_date"],
                y=asset_ts["health_score"],
                mode="lines",
                name=asset_id,
                line=dict(color=color, width=2),
                hovertemplate=f"<b>{asset_id}</b><br>Date: %{{x}}<br>Health: %{{y:.1f}}<extra></extra>",
            ))

        # Zone shading
        fig_ht.add_hrect(y0=0, y1=60, fillcolor="rgba(248,81,73,0.05)", line_width=0)
        fig_ht.add_hrect(y0=60, y1=80, fillcolor="rgba(210,153,34,0.05)", line_width=0)
        fig_ht.add_hline(y=80, line_dash="dash", line_color=THEME["green"],
                         line_width=1,
                         annotation_text="Good ≥80",
                         annotation_font=dict(size=9, color=THEME["green"]))
        fig_ht.add_hline(y=60, line_dash="dash", line_color=THEME["amber"],
                         line_width=1,
                         annotation_text="Fair ≥60",
                         annotation_font=dict(size=9, color=THEME["amber"]))

        apply_layout(fig_ht, height=340)
        fig_ht.update_layout(
            yaxis=dict(range=[30, 105], title="Health Score"),
            legend=dict(orientation="h", y=1.08, x=0),
            margin=dict(l=50, r=20, t=40, b=50),
        )
        st.plotly_chart(fig_ht, use_container_width=True, key="p5_asset_health_chart_1")

    st.markdown("<br>", unsafe_allow_html=True)

    # ── MAINTENANCE PRIORITY MATRIX ────────────────────────────────────────
    col_pri, col_risk = st.columns(2)

    with col_pri:
        section_header("Maintenance Priority Matrix")
        sorted_priority = kpis.sort_values("maintenance_priority_score", ascending=False)
        risk_colors_list = [RISK_COLORS.get(r, THEME["blue"]) for r in sorted_priority["risk_level"]]

        fig_pri = go.Figure(go.Bar(
            x=sorted_priority["asset_id"],
            y=sorted_priority["maintenance_priority_score"],
            marker_color=risk_colors_list,
            text=[f"{v:.0f}" for v in sorted_priority["maintenance_priority_score"]],
            textposition="outside",
            textfont=dict(size=11, color=THEME["text_primary"]),
            customdata=sorted_priority[["asset_name","risk_level","failure_probability_30d"]].values,
            hovertemplate=(
                "<b>%{customdata[0]}</b><br>"
                "Priority Score: %{y:.1f}<br>"
                "Risk: %{customdata[1]}<br>"
                "Fail Prob: %{customdata[2]:.1%}<extra></extra>"
            ),
        ))
        apply_layout(fig_pri, height=310)
        fig_pri.update_layout(
            yaxis_title="Priority Score",
            showlegend=False,
            margin=dict(l=40, r=20, t=20, b=50),
        )
        st.plotly_chart(fig_pri, use_container_width=True, key="p5_asset_health_chart_2")

    with col_risk:
        section_header("Risk Heatmap — Criticality × Failure Probability")
        fig_heat = go.Figure()

        x_labels = ["Low", "Medium", "High", "Critical"]
        y_labels = ["<20%", "20–40%", "40–60%", ">60%"]

        # Heatmap grid
        z = np.zeros((4, 4))
        asset_positions = []
        for _, row in kpis.iterrows():
            x_idx = min(int(row["criticality_score"]) - 1, 3)
            prob = row["failure_probability_30d"]
            y_idx = 0 if prob < 0.2 else (1 if prob < 0.4 else (2 if prob < 0.6 else 3))
            z[y_idx][x_idx] += 1
            asset_positions.append((x_idx, y_idx, row["asset_id"]))

        fig_heat.add_trace(go.Heatmap(
            z=z,
            x=x_labels,
            y=y_labels,
            colorscale=[
                [0.0, THEME["bg_elevated"]],
                [0.4, "rgba(210,153,34,0.4)"],
                [1.0, "rgba(248,81,73,0.7)"],
            ],
            showscale=False,
            text=[[str(int(v)) if v > 0 else "" for v in row] for row in z],
            texttemplate="%{text}",
            textfont=dict(size=16, color="white"),
        ))

        # Asset labels on heatmap
        for x_pos, y_pos, asset_id in asset_positions:
            fig_heat.add_annotation(
                x=x_labels[x_pos], y=y_labels[y_pos],
                text=asset_id,
                showarrow=False,
                font=dict(size=9, color=THEME["text_secondary"]),
                yshift=-12,
            )

        apply_layout(fig_heat, height=310)
        fig_heat.update_layout(
            xaxis_title="Asset Criticality",
            yaxis_title="30-Day Failure Probability",
            margin=dict(l=70, r=20, t=20, b=60),
        )
        st.plotly_chart(fig_heat, use_container_width=True, key="p5_asset_health_chart_3")

    st.markdown("<br>", unsafe_allow_html=True)

    # ── INSPECTION SCORES ─────────────────────────────────────────────────
    section_header("Latest Inspection Condition Scores by Asset")
    if not inspections.empty:
        latest_insp = inspections.sort_values("inspection_date").groupby("asset_id").last().reset_index()
        for _, row in latest_insp.iterrows():
            score = row["inspection_score"]
            color = THEME["green"] if score >= 85 else (THEME["amber"] if score >= 70 else THEME["red"])
            bar_width = int(score)
            st.markdown(f"""
            <div style="background:#0f2040;border:1px solid #1e3a5f;border-radius:6px;
                         padding:10px 16px;margin-bottom:6px;">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;">
                    <span style="font-size:13px;font-weight:600;color:#e8edf5;">
                        {row['asset_id']} — {row['asset_name']}
                    </span>
                    <span style="font-size:13px;font-weight:700;color:{color};">
                        {score:.1f}/100 — {row['overall_condition']}
                    </span>
                </div>
                <div style="background:#162848;border-radius:4px;height:8px;">
                    <div style="background:{color};width:{bar_width}%;height:8px;border-radius:4px;
                                transition:width 0.3s;"></div>
                </div>
                <div style="font-size:10px;color:#4d6a85;margin-top:4px;">
                    Inspected: {row['inspection_date']} · Findings: {int(row['findings_count'])} ·
                    Critical: {int(row['critical_findings'])} ·
                    Corrosion rate: {row['corrosion_rate_mm_yr']:.3f} mm/yr
                </div>
            </div>
            """, unsafe_allow_html=True)
