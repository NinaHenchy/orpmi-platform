"""
Page 7 — Failure Analysis
Purpose: Pareto analysis, failure mode distribution, FMEA-style register, bad actor identification.
Audience: Reliability Engineer, Maintenance Superintendent, Asset Integrity Manager
"""

import sys
from pathlib import Path
import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from dashboards.data_access import (
    get_failure_events, get_failure_pareto, get_failures_by_asset,
    get_failures_by_month, get_latest_kpis
)
from dashboards.components.ui_components import (
    inject_css, page_header, section_header, apply_layout, THEME, SEVERITY_COLORS, CRITICALITY_COLORS
)
from config.settings import ASSET_REGISTRY


def render_failure_analysis():
    inject_css()
    page_header(
        "Failure Analysis",
        "Pareto Analysis · Failure Mode Distribution · Bad Actor Register · RCFA Summary",
        "📋"
    )

    failures = get_failure_events()
    pareto = get_failure_pareto()
    by_asset = get_failures_by_asset()
    kpis = get_latest_kpis()

    if failures.empty:
        st.warning("No failure events in dataset.")
        return

    # ── SUMMARY ───────────────────────────────────────────────────────────
    section_header("Failure Analysis KPI Summary")
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1: st.metric("Total Failures YTD", len(failures))
    with c2: st.metric("Total Failure Modes", failures["failure_category"].nunique())
    with c3:
        recurrence_rate = failures["is_recurrence"].mean() * 100
        st.metric("Recurrence Rate", f"{recurrence_rate:.1f}%",
                  help="% of failures that are repeat occurrences on same asset/mode")
    with c4: st.metric("Avg Downtime/Failure", f"{failures['downtime_hours'].mean():.1f} hrs")
    with c5:
        top_cause = failures["failure_category"].value_counts().index[0]
        st.metric("Dominant Failure Mode", top_cause.split("/")[0])

    st.markdown("<br>", unsafe_allow_html=True)

    # ── PARETO CHART ──────────────────────────────────────────────────────
    section_header("Failure Mode Pareto — Count & Cumulative %")
    if not pareto.empty:
        cumulative_pct = pareto["pct_of_total"].cumsum()
        fig_pareto = make_subplots(specs=[[{"secondary_y": True}]])
        fig_pareto.add_trace(go.Bar(
            x=pareto["failure_category"],
            y=pareto["failure_count"],
            name="Failure Count",
            marker_color=THEME["red"],
            opacity=0.8,
        ), secondary_y=False)
        fig_pareto.add_trace(go.Scatter(
            x=pareto["failure_category"],
            y=cumulative_pct,
            mode="lines+markers",
            name="Cumulative %",
            line=dict(color=THEME["amber"], width=2.5),
            marker=dict(size=7),
        ), secondary_y=True)
        fig_pareto.add_hline(y=80, line_dash="dash", line_color=THEME["blue"],
                             line_width=1, secondary_y=True,
                             annotation_text="80% threshold",
                             annotation_font=dict(size=9, color=THEME["blue"]))
        apply_layout(fig_pareto, height=320)
        fig_pareto.update_yaxes(title_text="Failure Count", secondary_y=False,
                                gridcolor=THEME["grid_color"])
        fig_pareto.update_yaxes(title_text="Cumulative %", secondary_y=True,
                                range=[0, 110], showgrid=False,
                                tickfont=dict(color=THEME["amber"]))
        fig_pareto.update_layout(
            xaxis=dict(tickangle=-30, tickfont=dict(size=9)),
            legend=dict(orientation="h", y=1.1, x=0, font=dict(size=10)),
            margin=dict(l=50, r=70, t=30, b=100),
        )
        st.plotly_chart(fig_pareto, use_container_width=True, key="p7_failure_analysis_chart_1")

    st.markdown("<br>", unsafe_allow_html=True)

    # ── DOWNTIME PARETO + FINANCIAL PARETO ────────────────────────────────
    col_dt_pareto, col_fin_pareto = st.columns(2)

    with col_dt_pareto:
        section_header("Downtime by Failure Mode")
        if not pareto.empty:
            sorted_dt = pareto.sort_values("total_downtime_hrs", ascending=True)
            fig_dt_p = go.Figure(go.Bar(
                x=sorted_dt["total_downtime_hrs"],
                y=sorted_dt["failure_category"],
                orientation="h",
                marker_color=[THEME["red"], THEME["amber"], THEME["orange"],
                              THEME["blue"], THEME["purple"]] * 4,
                text=[f"{v:.1f} hrs" for v in sorted_dt["total_downtime_hrs"]],
                textposition="outside",
                textfont=dict(size=9),
            ))
            apply_layout(fig_dt_p, height=300)
            fig_dt_p.update_layout(
                xaxis_title="Total Downtime (hrs)",
                margin=dict(l=180, r=60, t=20, b=40),
                showlegend=False,
            )
            st.plotly_chart(fig_dt_p, use_container_width=True, key="p7_failure_analysis_chart_2")

    with col_fin_pareto:
        section_header("Financial Impact by Failure Mode")
        if not pareto.empty:
            sorted_fin = pareto.sort_values("total_impact_usd", ascending=True)
            fig_fin_p = go.Figure(go.Bar(
                x=sorted_fin["total_impact_usd"],
                y=sorted_fin["failure_category"],
                orientation="h",
                marker_color=THEME["amber"],
                opacity=0.8,
                text=[f"${v:,.0f}" for v in sorted_fin["total_impact_usd"]],
                textposition="outside",
                textfont=dict(size=9),
            ))
            apply_layout(fig_fin_p, height=300)
            fig_fin_p.update_layout(
                xaxis_title="Financial Impact (USD)",
                margin=dict(l=180, r=80, t=20, b=40),
                showlegend=False,
            )
            st.plotly_chart(fig_fin_p, use_container_width=True, key="p7_failure_analysis_chart_3")

    st.markdown("<br>", unsafe_allow_html=True)

    # ── BAD ACTOR REGISTER ────────────────────────────────────────────────
    section_header("Bad Actor Register — Assets with Highest Failure Impact")
    if not by_asset.empty:
        by_asset_display = by_asset.copy()
        by_asset_display["total_impact_usd"] = by_asset_display["total_impact_usd"].apply(
            lambda x: f"${x:,.0f}"
        )
        by_asset_display["avg_ttr_hrs"] = by_asset_display["avg_ttr_hrs"].round(1)
        by_asset_display["total_downtime_hrs"] = by_asset_display["total_downtime_hrs"].round(1)
        by_asset_display.columns = [
            "Asset ID", "Asset Name", "Criticality", "Total Failures",
            "Total Downtime hrs", "Financial Impact", "Avg TTR hrs", "Critical Failures"
        ]

        # Highlight top bad actor
        if not by_asset_display.empty:
            top_bad = by_asset.iloc[0]
            st.markdown(f"""
            <div style="background:#1a0808;border:1px solid #ef4444;border-left:4px solid #ef4444;
                         border-radius:6px;padding:12px 16px;margin-bottom:12px;">
                <span style="color:#ef4444;font-weight:700;">🔴 BAD ACTOR:</span>
                <span style="color:#e8edf5;margin-left:8px;font-weight:600;">
                    {top_bad['asset_id']} — {top_bad['asset_name']}
                </span>
                <span style="color:#4d6a85;margin-left:12px;font-size:12px;">
                    {int(top_bad['total_failures'])} failures ·
                    {top_bad['total_downtime_hrs']:.1f} hrs downtime ·
                    ${top_bad['total_impact_usd']:,.0f} financial impact
                </span>
            </div>
            """, unsafe_allow_html=True)

        st.dataframe(by_asset_display, use_container_width=True, hide_index=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── FAILURE TIMELINE ──────────────────────────────────────────────────
    section_header("Failure Event Timeline — Severity & Downtime")
    failures_sorted = failures.sort_values("failure_date")
    colors_sev = [SEVERITY_COLORS.get(s, THEME["blue"])
                  for s in failures_sorted["failure_severity"]]

    fig_timeline = go.Figure(go.Scatter(
        x=failures_sorted["failure_date"],
        y=failures_sorted["asset_id"],
        mode="markers",
        marker=dict(
            size=failures_sorted["downtime_hours"].clip(lower=3, upper=30),
            color=colors_sev,
            opacity=0.85,
            line=dict(color=THEME["border"], width=1),
        ),
        customdata=failures_sorted[[
            "asset_name", "failure_category", "failure_severity",
            "downtime_hours", "financial_impact_usd"
        ]].values,
        hovertemplate=(
            "<b>%{customdata[0]}</b><br>"
            "Date: %{x}<br>"
            "Category: %{customdata[1]}<br>"
            "Severity: %{customdata[2]}<br>"
            "Downtime: %{customdata[3]:.1f} hrs<br>"
            "Impact: $%{customdata[4]:,.0f}<extra></extra>"
        ),
        text=failures_sorted["failure_severity"],
    ))
    apply_layout(fig_timeline, height=280)
    fig_timeline.update_layout(
        yaxis=dict(title="Asset"),
        xaxis=dict(title="Date"),
        showlegend=False,
        margin=dict(l=80, r=20, t=20, b=60),
    )

    # Add legend manually
    for severity, color in SEVERITY_COLORS.items():
        fig_timeline.add_trace(go.Scatter(
            x=[None], y=[None], mode="markers",
            marker=dict(size=10, color=color),
            name=severity, showlegend=True,
        ))
    fig_timeline.update_layout(
        legend=dict(orientation="h", y=1.1, x=0, font=dict(size=10)),
    )
    st.plotly_chart(fig_timeline, use_container_width=True, key="p7_failure_analysis_chart_4")

    st.markdown("<br>", unsafe_allow_html=True)

    # ── DETAILED FAILURE LOG WITH RCFA ────────────────────────────────────
    section_header("Failure Detail Register — Root Cause & Corrective Actions")
    tabs = st.tabs(["All Failures", "Critical & Major", "Recurring Failures"])

    def render_failure_table(df):
        cols = ["failure_date","asset_id","failure_category","failure_severity",
                "downtime_hours","financial_impact_usd","root_cause","corrective_action"]
        display = df[cols].copy()
        display.columns = ["Date","Asset","Category","Severity","Downtime hrs",
                           "Impact $","Root Cause","Corrective Action"]
        display["Impact $"] = display["Impact $"].apply(lambda x: f"${x:,.0f}")
        display["Root Cause"] = display["Root Cause"].str[:100]
        display["Corrective Action"] = display["Corrective Action"].str[:100]
        st.dataframe(display, use_container_width=True, hide_index=True, height=300)

    with tabs[0]:
        render_failure_table(failures)
    with tabs[1]:
        critical_major = failures[failures["failure_severity"].isin(["Critical","Major"])]
        if not critical_major.empty:
            render_failure_table(critical_major)
        else:
            st.info("No Critical or Major failures in this period.")
    with tabs[2]:
        recurring = failures[failures["is_recurrence"] == 1]
        if not recurring.empty:
            render_failure_table(recurring)
            st.warning(f"⚠ {len(recurring)} recurring failures identified. Engineering review recommended for all recurrent failure modes.")
        else:
            st.success("No recurring failures identified in this period.")
