"""
Page 3 — Downtime Analysis
Purpose: Full downtime cost tracking, Pareto, and production loss visibility.
Audience: Operations Manager, Maintenance Superintendent, Production Manager
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
    get_failure_events, get_downtime_log, get_latest_kpis,
    get_failures_by_asset, get_failures_by_month
)
from dashboards.components.ui_components import (
    inject_css, page_header, section_header, apply_layout, THEME, SEVERITY_COLORS
)
from config.settings import ASSET_REGISTRY


def render_downtime_analysis():
    inject_css()
    page_header(
        "Downtime Analysis",
        "Unplanned Downtime · Production Loss · Financial Impact · Root Cause Distribution",
        "⏱️"
    )

    failures = get_failure_events()
    downtime_log = get_downtime_log()
    kpis = get_latest_kpis()

    if failures.empty:
        st.warning("No failure events found in the current dataset.")
        return

    # ── FINANCIAL SUMMARY METRICS ─────────────────────────────────────────
    section_header("Downtime Financial Impact — YTD Summary")

    total_dt_hrs   = failures["downtime_hours"].sum()
    total_prod_loss = failures["production_loss_bbls"].sum()
    total_impact   = failures["financial_impact_usd"].sum()
    critical_count = len(failures[failures["failure_severity"] == "Critical"])
    avg_ttr = failures["time_to_repair_hrs"].mean()

    c1, c2, c3, c4, c5 = st.columns(5)
    with c1: st.metric("Total Downtime hrs", f"{total_dt_hrs:.1f}")
    with c2: st.metric("Total Financial Impact", f"${total_impact/1e6:.2f}M")
    with c3: st.metric("Production Loss", f"{total_prod_loss:,.0f} bbls")
    with c4: st.metric("Critical Failures", critical_count,
                       f"{critical_count/len(failures)*100:.0f}% of all events")
    with c5: st.metric("Avg TTR", f"{avg_ttr:.1f} hrs")

    st.markdown("<br>", unsafe_allow_html=True)

    # ── DOWNTIME BY ASSET + FINANCIAL IMPACT ─────────────────────────────
    col_left, col_right = st.columns(2)

    with col_left:
        section_header("Downtime Hours by Asset")
        dt_by_asset = failures.groupby(["asset_id", "asset_name"]).agg(
            total_downtime=("downtime_hours", "sum"),
            events=("work_order_id", "count"),
        ).reset_index().sort_values("total_downtime", ascending=True)

        fig_dt = go.Figure(go.Bar(
            x=dt_by_asset["total_downtime"],
            y=dt_by_asset["asset_name"],
            orientation="h",
            marker_color=[THEME["asset_colors"].get(aid, THEME["blue"])
                          for aid in dt_by_asset["asset_id"]],
            text=[f"{v:.1f} hrs" for v in dt_by_asset["total_downtime"]],
            textposition="outside",
            customdata=dt_by_asset[["events", "asset_id"]].values,
            hovertemplate=(
                "<b>%{y}</b><br>Downtime: %{x:.1f} hrs<br>"
                "Events: %{customdata[0]}<extra></extra>"
            ),
        ))
        apply_layout(fig_dt, height=290)
        fig_dt.update_layout(
            xaxis_title="Total Downtime (hrs)",
            margin=dict(l=160, r=50, t=20, b=40),
            showlegend=False,
        )
        st.plotly_chart(fig_dt, use_container_width=True, key="p3_chart_dt_asset")

    with col_right:
        section_header("Financial Impact by Asset")
        fin_by_asset = []
        for asset_id, info in ASSET_REGISTRY.items():
            asset_f = failures[failures["asset_id"] == asset_id]
            if asset_f.empty:
                continue
            cost = asset_f["downtime_hours"].sum() * info["downtime_cost_usd_per_hr"]
            fin_by_asset.append({"asset_id": asset_id, "name": info["name"], "cost": cost})
        fin_df = pd.DataFrame(fin_by_asset).sort_values("cost", ascending=True)

        if not fin_df.empty:
            fig_fin = go.Figure(go.Bar(
                x=fin_df["cost"],
                y=fin_df["name"],
                orientation="h",
                marker_color=[THEME["asset_colors"].get(aid, THEME["red"])
                              for aid in fin_df["asset_id"]],
                text=[f"${v:,.0f}" for v in fin_df["cost"]],
                textposition="outside",
                textfont=dict(size=10),
            ))
            apply_layout(fig_fin, height=290)
            fig_fin.update_layout(
                xaxis_title="Downtime Cost (USD)",
                margin=dict(l=160, r=80, t=20, b=40),
                showlegend=False,
            )
            st.plotly_chart(fig_fin, use_container_width=True, key="p3_chart_fin_asset")

    st.markdown("<br>", unsafe_allow_html=True)

    # ── MONTHLY DOWNTIME TREND ─────────────────────────────────────────────
    section_header("Monthly Downtime Trend — Hours & Financial Impact")
    monthly = get_failures_by_month()
    if not monthly.empty:
        monthly_agg = monthly.groupby("month").agg(
            total_downtime=("total_downtime", "sum"),
            total_impact=("total_impact", "sum"),
            total_failures=("failures", "sum"),
        ).reset_index()

        fig_monthly = make_subplots(specs=[[{"secondary_y": True}]])
        fig_monthly.add_trace(go.Bar(
            x=monthly_agg["month"],
            y=monthly_agg["total_downtime"],
            name="Downtime hrs",
            marker_color=THEME["red"],
            opacity=0.75,
        ), secondary_y=False)
        fig_monthly.add_trace(go.Scatter(
            x=monthly_agg["month"],
            y=monthly_agg["total_impact"],
            mode="lines+markers",
            name="Financial Impact $",
            line=dict(color=THEME["amber"], width=2.5),
            marker=dict(size=7),
        ), secondary_y=True)
        apply_layout(fig_monthly, height=320)
        fig_monthly.update_yaxes(
            title_text="Downtime Hours", secondary_y=False,
            gridcolor=THEME["grid_color"], tickfont=dict(size=10)
        )
        fig_monthly.update_yaxes(
            title_text="Financial Impact (USD)", secondary_y=True,
            showgrid=False, tickfont=dict(size=10, color=THEME["amber"])
        )
        fig_monthly.update_layout(
            legend=dict(orientation="h", y=1.1, x=0, font=dict(size=10)),
            margin=dict(l=60, r=70, t=30, b=50),
        )
        st.plotly_chart(fig_monthly, use_container_width=True, key="p3_chart_monthly")

    st.markdown("<br>", unsafe_allow_html=True)

    # ── SEVERITY + CATEGORY ───────────────────────────────────────────────
    col_sev, col_det = st.columns(2)

    with col_sev:
        section_header("Failure Severity Distribution")
        sev_counts = failures["failure_severity"].value_counts()
        sev_order = ["Critical", "Major", "Minor", "Negligible"]
        sev_filtered = {k: sev_counts.get(k, 0) for k in sev_order if sev_counts.get(k, 0) > 0}

        fig_sev = go.Figure(go.Pie(
            labels=list(sev_filtered.keys()),
            values=list(sev_filtered.values()),
            marker_colors=[SEVERITY_COLORS[k] for k in sev_filtered.keys()],
            hole=0.5,
            textinfo="label+percent",
            textfont=dict(size=11),
            hovertemplate="<b>%{label}</b><br>Count: %{value}<br>%{percent}<extra></extra>",
        ))
        apply_layout(fig_sev, height=280)
        fig_sev.update_layout(
            showlegend=True,
            legend=dict(orientation="h", y=-0.15, x=0.1, font=dict(size=10)),
            margin=dict(l=20, r=20, t=20, b=60),
        )
        st.plotly_chart(fig_sev, use_container_width=True, key="p3_chart_severity")

    with col_det:
        section_header("Downtime by Failure Category")
        cat_dt = failures.groupby("failure_category").agg(
            total_downtime=("downtime_hours", "sum"),
            count=("work_order_id", "count"),
        ).reset_index().sort_values("total_downtime", ascending=False).head(8)

        colors_cat = [
            THEME["blue"], THEME["red"], THEME["amber"], THEME["green"],
            THEME["purple"], THEME["cyan"], THEME["orange"], THEME["text_secondary"]
        ]

        fig_cat = go.Figure(go.Bar(
            x=cat_dt["failure_category"],
            y=cat_dt["total_downtime"],
            marker_color=colors_cat[:len(cat_dt)],
            text=[f"{v:.1f}h" for v in cat_dt["total_downtime"]],
            textposition="outside",
            textfont=dict(size=10),
        ))
        apply_layout(fig_cat, height=280)
        fig_cat.update_layout(
            yaxis_title="Total Downtime (hrs)",
            xaxis=dict(tickangle=-35, tickfont=dict(size=9)),
            showlegend=False,
            margin=dict(l=40, r=20, t=20, b=90),
        )
        st.plotly_chart(fig_cat, use_container_width=True, key="p3_chart_category")

    st.markdown("<br>", unsafe_allow_html=True)

    # ── FAILURE EVENT LOG ──────────────────────────────────────────────────
    section_header("Failure Event Register — Complete Log")
    display_cols = [
        "failure_date", "asset_id", "asset_name", "failure_category",
        "failure_severity", "downtime_hours", "time_to_repair_hrs",
        "financial_impact_usd", "detection_method", "root_cause"
    ]
    log_df = failures[display_cols].copy()
    log_df.columns = [
        "Date", "Asset ID", "Asset Name", "Category", "Severity",
        "Downtime hrs", "TTR hrs", "Financial Impact $", "Detection", "Root Cause"
    ]
    log_df["Financial Impact $"] = log_df["Financial Impact $"].apply(lambda x: f"${x:,.0f}")
    log_df["Root Cause"] = log_df["Root Cause"].str[:80] + "..."
    st.dataframe(log_df, use_container_width=True, hide_index=True, height=350)