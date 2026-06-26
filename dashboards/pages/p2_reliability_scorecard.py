"""
Page 2 — Reliability Scorecard
Purpose: Deep-dive into MTBF, MTTR, availability trends, and reliability ranking per asset.
Audience: Reliability Engineer, Asset Integrity Manager, Maintenance Superintendent
"""

import sys
from pathlib import Path
import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from dashboards.data_access import get_latest_kpis, get_kpi_timeseries, get_monthly_kpis
from dashboards.components.ui_components import (
    inject_css, page_header, section_header, apply_layout, THEME, RISK_COLORS
)
from config.settings import ASSET_REGISTRY, KPI_THRESHOLDS


def render_reliability_scorecard():
    inject_css()
    page_header(
        "Reliability Scorecard",
        "Asset-level MTBF · MTTR · Availability · Reliability Score — Rolling Analysis",
        "📊"
    )

    kpis = get_latest_kpis()
    monthly = get_monthly_kpis()
    timeseries = get_kpi_timeseries()

    if kpis.empty:
        st.error("No KPI data available.")
        return

    # ── FILTERS ───────────────────────────────────────────────────────────
    with st.expander("🔎 Filters", expanded=False):
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            selected_assets = st.multiselect(
                "Filter Assets",
                options=kpis["asset_id"].tolist(),
                default=kpis["asset_id"].tolist(),
                format_func=lambda x: f"{x} — {ASSET_REGISTRY[x]['name']}"
            )
        with col_f2:
            crit_filter = st.multiselect(
                "Filter Criticality",
                options=["Critical", "High", "Medium", "Low"],
                default=["Critical", "High", "Medium", "Low"]
            )

    filtered_kpis = kpis[
        (kpis["asset_id"].isin(selected_assets)) &
        (kpis["criticality"].isin(crit_filter))
    ]

    # ── SCORECARD METRICS ─────────────────────────────────────────────────
    section_header("Reliability KPI Scorecard — Current Period")
    for _, row in filtered_kpis.iterrows():
        avail_color = THEME["green"] if row["availability_pct"] >= 97 else (
            THEME["amber"] if row["availability_pct"] >= 93 else THEME["red"])
        health_color = THEME["green"] if row["health_score"] >= 80 else (
            THEME["amber"] if row["health_score"] >= 60 else THEME["red"])
        risk_color = RISK_COLORS.get(row["risk_level"], THEME["blue"])
        target_avail = row["target_availability_pct"]
        avail_vs_target = row["availability_pct"] - target_avail

        with st.container():
            st.markdown(f"""
            <div style="background:#0f2040;border:1px solid #1e3a5f;border-left:4px solid {avail_color};
                         border-radius:8px;padding:14px 20px;margin-bottom:10px;">
                <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:12px;">
                    <div style="min-width:200px;">
                        <div style="font-size:14px;font-weight:700;color:#e8edf5;">{row['asset_id']} — {row['asset_name']}</div>
                        <div style="font-size:11px;color:#4d6a85;margin-top:2px;">
                            {row['asset_type']} · {row['criticality']} ·
                            <span style="color:{risk_color};font-weight:600;">{row['risk_level']} Risk</span>
                        </div>
                    </div>
                    <div style="text-align:center;">
                        <div style="font-size:10px;color:#4d6a85;text-transform:uppercase;">Availability</div>
                        <div style="font-size:22px;font-weight:700;color:{avail_color};">{row['availability_pct']:.1f}%</div>
                        <div style="font-size:10px;color:#4d6a85;">Target {target_avail}% · {"▲" if avail_vs_target>=0 else "▼"}{abs(avail_vs_target):.1f}%</div>
                    </div>
                    <div style="text-align:center;">
                        <div style="font-size:10px;color:#4d6a85;text-transform:uppercase;">MTBF</div>
                        <div style="font-size:22px;font-weight:700;color:#e8edf5;">{int(row['mtbf_hrs'])} hrs</div>
                        <div style="font-size:10px;color:#4d6a85;">{row['mtbf_hrs']/24:.1f} days avg</div>
                    </div>
                    <div style="text-align:center;">
                        <div style="font-size:10px;color:#4d6a85;text-transform:uppercase;">MTTR</div>
                        <div style="font-size:22px;font-weight:700;color:#e8edf5;">{row['mttr_hrs']:.1f} hrs</div>
                        <div style="font-size:10px;color:#4d6a85;">Repair time avg</div>
                    </div>
                    <div style="text-align:center;">
                        <div style="font-size:10px;color:#4d6a85;text-transform:uppercase;">Health</div>
                        <div style="font-size:22px;font-weight:700;color:{health_color};">{row['health_score']:.1f}</div>
                        <div style="font-size:10px;color:#4d6a85;">out of 100</div>
                    </div>
                    <div style="text-align:center;">
                        <div style="font-size:10px;color:#4d6a85;text-transform:uppercase;">Reliability</div>
                        <div style="font-size:22px;font-weight:700;color:#e8edf5;">{row['reliability_score']:.1f}</div>
                        <div style="font-size:10px;color:#4d6a85;">Composite score</div>
                    </div>
                    <div style="text-align:center;">
                        <div style="font-size:10px;color:#4d6a85;text-transform:uppercase;">Compliance</div>
                        <div style="font-size:22px;font-weight:700;color:{'#00d4aa' if row['maintenance_compliance_pct']>=90 else '#f59e0b'};">{row['maintenance_compliance_pct']:.1f}%</div>
                        <div style="font-size:10px;color:#4d6a85;">PM on-schedule</div>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── MTBF vs MTTR COMPARISON ────────────────────────────────────────────
    col_mtbf, col_mttr = st.columns(2)

    with col_mtbf:
        section_header("MTBF Comparison — All Assets")
        fig_mtbf = go.Figure()
        sorted_kpis = filtered_kpis.sort_values("mtbf_hrs", ascending=True)
        colors = [THEME["green"] if v >= 720 else (THEME["amber"] if v >= 360 else THEME["red"])
                  for v in sorted_kpis["mtbf_hrs"]]
        fig_mtbf.add_trace(go.Bar(
            x=sorted_kpis["mtbf_hrs"],
            y=sorted_kpis["asset_id"],
            orientation="h",
            marker_color=colors,
            text=[f"{int(v)} hrs" for v in sorted_kpis["mtbf_hrs"]],
            textposition="outside",
            textfont=dict(size=10, color=THEME["text_primary"]),
        ))
        fig_mtbf.add_vline(x=720, line_dash="dash", line_color=THEME["green"],
                           line_width=1.2,
                           annotation_text="Target 720 hrs",
                           annotation_font=dict(size=9, color=THEME["green"]))
        apply_layout(fig_mtbf, height=300)
        fig_mtbf.update_layout(
            xaxis_title="MTBF (hours)",
            showlegend=False,
            margin=dict(l=80, r=60, t=20, b=40),
        )
        st.plotly_chart(fig_mtbf, use_container_width=True, key="p2_reliability_scorecard_chart_1")

    with col_mttr:
        section_header("MTTR Comparison — All Assets")
        sorted_mttr = filtered_kpis.sort_values("mttr_hrs", ascending=False)
        colors_mttr = [THEME["red"] if v > 12 else (THEME["amber"] if v > 8 else THEME["green"])
                       for v in sorted_mttr["mttr_hrs"]]
        fig_mttr = go.Figure()
        fig_mttr.add_trace(go.Bar(
            x=sorted_mttr["mttr_hrs"],
            y=sorted_mttr["asset_id"],
            orientation="h",
            marker_color=colors_mttr,
            text=[f"{v:.1f} hrs" for v in sorted_mttr["mttr_hrs"]],
            textposition="outside",
            textfont=dict(size=10),
        ))
        fig_mttr.add_vline(x=8, line_dash="dash", line_color=THEME["amber"],
                           line_width=1.2,
                           annotation_text="Target ≤8 hrs",
                           annotation_font=dict(size=9, color=THEME["amber"]))
        apply_layout(fig_mttr, height=300)
        fig_mttr.update_layout(
            xaxis_title="MTTR (hours)",
            showlegend=False,
            margin=dict(l=80, r=60, t=20, b=40),
        )
        st.plotly_chart(fig_mttr, use_container_width=True, key="p2_reliability_scorecard_chart_2")

    st.markdown("<br>", unsafe_allow_html=True)

    # ── AVAILABILITY TREND — MONTHLY ───────────────────────────────────────
    section_header("Monthly Availability Trend — Asset Comparison")
    if not monthly.empty:
        asset_options = filtered_kpis["asset_id"].tolist()
        fig_avail_trend = go.Figure()
        for asset_id in asset_options:
            asset_monthly = monthly[monthly["asset_id"] == asset_id]
            if asset_monthly.empty:
                continue
            color = THEME["asset_colors"].get(asset_id, THEME["blue"])
            asset_name = ASSET_REGISTRY[asset_id]["name"]
            fig_avail_trend.add_trace(go.Scatter(
                x=asset_monthly["year_month"],
                y=asset_monthly["avg_availability"],
                mode="lines+markers",
                name=f"{asset_id}",
                line=dict(color=color, width=2),
                marker=dict(size=6),
                hovertemplate=f"<b>{asset_name}</b><br>Month: %{{x}}<br>Availability: %{{y:.1f}}%<extra></extra>",
            ))
        fig_avail_trend.add_hline(y=97.0, line_dash="dot",
                                  line_color=THEME["amber"], line_width=1.5,
                                  annotation_text="Fleet Target 97%",
                                  annotation_font=dict(size=9, color=THEME["amber"]))
        apply_layout(fig_avail_trend, height=360)
        fig_avail_trend.update_layout(
            yaxis=dict(title="Availability %", range=[80, 102]),
            xaxis=dict(title="Month"),
            legend=dict(orientation="h", y=1.1, x=0),
            margin=dict(l=50, r=20, t=40, b=50),
        )
        st.plotly_chart(fig_avail_trend, use_container_width=True, key="p2_reliability_scorecard_chart_3")

    # ── RELIABILITY RANKING ─────────────────────────────────────────────────
    section_header("Asset Reliability Ranking — Composite Score")
    ranked = filtered_kpis.sort_values("reliability_score", ascending=False).reset_index(drop=True)
    ranked["Rank"] = ranked.index + 1

    fig_rank = go.Figure()
    bar_colors = [THEME["asset_colors"].get(aid, THEME["blue"]) for aid in ranked["asset_id"]]
    fig_rank.add_trace(go.Bar(
        x=ranked["asset_id"],
        y=ranked["reliability_score"],
        marker_color=bar_colors,
        text=[f"{v:.1f}" for v in ranked["reliability_score"]],
        textposition="outside",
        textfont=dict(size=12, color=THEME["text_primary"]),
        customdata=ranked[["asset_name","availability_pct","health_score","mtbf_hrs"]].values,
        hovertemplate=(
            "<b>%{customdata[0]}</b><br>"
            "Reliability Score: %{y:.1f}<br>"
            "Availability: %{customdata[1]:.1f}%<br>"
            "Health: %{customdata[2]:.1f}<br>"
            "MTBF: %{customdata[3]:.0f} hrs<extra></extra>"
        ),
    ))
    fig_rank.add_hline(y=85, line_dash="dash", line_color=THEME["green"],
                       line_width=1, annotation_text="Target 85",
                       annotation_font=dict(size=9, color=THEME["green"]))
    apply_layout(fig_rank, height=300)
    fig_rank.update_layout(
        yaxis=dict(range=[50, 105], title="Reliability Score"),
        showlegend=False,
        margin=dict(l=40, r=20, t=30, b=50),
    )
    st.plotly_chart(fig_rank, use_container_width=True, key="p2_reliability_scorecard_chart_4")
