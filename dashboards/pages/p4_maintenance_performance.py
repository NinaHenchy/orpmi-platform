"""
Page 4 — Maintenance Performance
Purpose: PM compliance, cost tracking, work order analysis, maintenance type distribution.
Audience: Maintenance Superintendent, Reliability Engineer, Operations Manager
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
    get_maintenance_records, get_maintenance_cost_by_type,
    get_maintenance_compliance_by_asset, get_latest_kpis
)
from dashboards.components.ui_components import (
    inject_css, page_header, section_header, apply_layout, alert_banner, THEME
)
from config.settings import ASSET_REGISTRY


def render_maintenance_performance():
    inject_css()
    page_header(
        "Maintenance Performance",
        "PM Compliance · Work Order Analysis · Maintenance Cost · Overdue Tracking",
        "🔧"
    )

    maint = get_maintenance_records()
    cost_by_type = get_maintenance_cost_by_type()
    compliance_by_asset = get_maintenance_compliance_by_asset()
    kpis = get_latest_kpis()

    if maint.empty:
        st.warning("No maintenance records found.")
        return

    # Overdue alerts
    overdue = maint[maint["overdue_days"] > 0]
    if not overdue.empty:
        alert_banner(
            f"{len(overdue)} work order(s) were executed overdue. "
            f"Avg overdue: {overdue['overdue_days'].mean():.0f} days. "
            f"Review maintenance scheduling adherence.",
            level="warning"
        )

    # ── SUMMARY METRICS ───────────────────────────────────────────────────
    section_header("Maintenance KPI Summary")
    total_cost = maint["actual_cost_usd"].sum()
    total_wo = len(maint)
    pm_wo = len(maint[maint["maintenance_type"] == "Preventive Maintenance"])
    cm_wo = len(maint[maint["maintenance_type"].isin(["Corrective Maintenance","Breakdown Maintenance"])])
    compliance_overall = maint["compliance_flag"].mean() * 100
    failures_prevented = maint["failure_prevented"].sum()

    c1, c2, c3, c4, c5, c6 = st.columns(6)
    with c1: st.metric("Total Work Orders", total_wo)
    with c2: st.metric("Preventive WOs", pm_wo, f"{pm_wo/total_wo*100:.0f}% of total")
    with c3: st.metric("Total Maint Cost", f"${total_cost:,.0f}")
    with c4: st.metric("PM Compliance", f"{compliance_overall:.1f}%",
                       "vs 90% target" if compliance_overall < 90 else "✓ Above target")
    with c5: st.metric("Overdue WOs", len(overdue))
    with c6: st.metric("Failures Prevented", int(failures_prevented),
                       "via CBM/PM findings")

    st.markdown("<br>", unsafe_allow_html=True)

    # ── COMPLIANCE BY ASSET + COST BY TYPE ────────────────────────────────
    col_l, col_r = st.columns(2)

    with col_l:
        section_header("PM Compliance by Asset")
        if not compliance_by_asset.empty:
            sorted_comp = compliance_by_asset.sort_values("compliance_pct", ascending=True)
            comp_colors = [
                THEME["green"] if v >= 90 else (THEME["amber"] if v >= 75 else THEME["red"])
                for v in sorted_comp["compliance_pct"]
            ]
            fig_comp = go.Figure(go.Bar(
                x=sorted_comp["compliance_pct"],
                y=sorted_comp["asset_name"],
                orientation="h",
                marker_color=comp_colors,
                text=[f"{v:.1f}%" for v in sorted_comp["compliance_pct"]],
                textposition="outside",
                customdata=sorted_comp[["total_wo","avg_overdue_days"]].values,
                hovertemplate=(
                    "<b>%{y}</b><br>Compliance: %{x:.1f}%<br>"
                    "Total WOs: %{customdata[0]}<br>"
                    "Avg Overdue: %{customdata[1]:.1f} days<extra></extra>"
                ),
            ))
            fig_comp.add_vline(x=90, line_dash="dash", line_color=THEME["green"],
                               line_width=1.5,
                               annotation_text="Target 90%",
                               annotation_font=dict(size=9, color=THEME["green"]))
            apply_layout(fig_comp, height=300)
            fig_comp.update_layout(
                xaxis=dict(range=[0, 115], title="Compliance %"),
                margin=dict(l=170, r=50, t=20, b=40),
                showlegend=False,
            )
            st.plotly_chart(fig_comp, use_container_width=True, key="p4_maintenance_performance_chart_1")

    with col_r:
        section_header("Maintenance Cost by Type")
        if not cost_by_type.empty:
            cost_colors = [THEME["blue"], THEME["red"], THEME["amber"],
                           THEME["green"], THEME["purple"], THEME["cyan"]]
            fig_cost = go.Figure(go.Bar(
                x=cost_by_type["maintenance_type"],
                y=cost_by_type["total_cost"],
                marker_color=cost_colors[:len(cost_by_type)],
                text=[f"${v:,.0f}" for v in cost_by_type["total_cost"]],
                textposition="outside",
                textfont=dict(size=9),
                customdata=cost_by_type[["work_orders","avg_duration_hrs"]].values,
                hovertemplate=(
                    "<b>%{x}</b><br>Total Cost: $%{y:,.0f}<br>"
                    "Work Orders: %{customdata[0]}<br>"
                    "Avg Duration: %{customdata[1]:.1f} hrs<extra></extra>"
                ),
            ))
            apply_layout(fig_cost, height=300)
            fig_cost.update_layout(
                yaxis_title="Total Cost (USD)",
                xaxis=dict(tickangle=-30, tickfont=dict(size=9)),
                showlegend=False,
                margin=dict(l=50, r=20, t=20, b=90),
            )
            st.plotly_chart(fig_cost, use_container_width=True, key="p4_maintenance_performance_chart_2")

    st.markdown("<br>", unsafe_allow_html=True)

    # ── MAINTENANCE TYPE PIE + COST PER ASSET ──────────────────────────────
    col_pie, col_asset_cost = st.columns(2)

    with col_pie:
        section_header("Work Order Type Distribution")
        type_counts = maint["maintenance_type"].value_counts()
        fig_pie = go.Figure(go.Pie(
            labels=type_counts.index.tolist(),
            values=type_counts.values.tolist(),
            hole=0.45,
            marker_colors=[THEME["blue"], THEME["red"], THEME["amber"],
                           THEME["green"], THEME["purple"], THEME["cyan"],
                           THEME["orange"]],
            textinfo="percent+label",
            textfont=dict(size=10),
        ))
        apply_layout(fig_pie, height=290)
        fig_pie.update_layout(
            showlegend=False,
            margin=dict(l=10, r=10, t=20, b=20),
        )
        st.plotly_chart(fig_pie, use_container_width=True, key="p4_maintenance_performance_chart_3")

    with col_asset_cost:
        section_header("Maintenance Spend by Asset")
        cost_by_asset = maint.groupby("asset_id").agg(
            total_cost=("actual_cost_usd","sum"),
            wo_count=("work_order_id","count"),
        ).reset_index()
        cost_by_asset["asset_name"] = cost_by_asset["asset_id"].map(
            {k: v["name"] for k, v in ASSET_REGISTRY.items()}
        )
        cost_by_asset = cost_by_asset.sort_values("total_cost", ascending=True)
        fig_asset_cost = go.Figure(go.Bar(
            x=cost_by_asset["total_cost"],
            y=cost_by_asset["asset_name"],
            orientation="h",
            marker_color=[THEME["asset_colors"].get(aid, THEME["blue"])
                          for aid in cost_by_asset["asset_id"]],
            text=[f"${v:,.0f}" for v in cost_by_asset["total_cost"]],
            textposition="outside",
            textfont=dict(size=10),
        ))
        apply_layout(fig_asset_cost, height=290)
        fig_asset_cost.update_layout(
            xaxis_title="Total Maintenance Cost (USD)",
            margin=dict(l=180, r=80, t=20, b=40),
            showlegend=False,
        )
        st.plotly_chart(fig_asset_cost, use_container_width=True, key="p4_maintenance_performance_chart_4")

    st.markdown("<br>", unsafe_allow_html=True)

    # ── WORK ORDER REGISTER ────────────────────────────────────────────────
    section_header("Work Order Register")
    tabs = st.tabs(["All Work Orders", "Overdue WOs", "Failures Prevented"])

    with tabs[0]:
        cols = ["work_order_id","asset_id","asset_name","maintenance_type",
                "maintenance_date","scheduled_date","actual_cost_usd",
                "duration_hrs","compliance_flag","overdue_days","inspection_score"]
        wo_df = maint[cols].copy()
        wo_df.columns = ["WO ID","Asset ID","Asset Name","Type","Date","Scheduled",
                         "Cost $","Duration hrs","Compliant","Overdue Days","Inspection Score"]
        wo_df["Cost $"] = wo_df["Cost $"].apply(lambda x: f"${x:,.0f}")
        wo_df["Compliant"] = wo_df["Compliant"].map({1: "✅ Yes", 0: "❌ No"})
        st.dataframe(wo_df, use_container_width=True, hide_index=True, height=320)

    with tabs[1]:
        if not overdue.empty:
            od_cols = ["work_order_id","asset_name","maintenance_type",
                       "maintenance_date","scheduled_date","overdue_days","actual_cost_usd"]
            od_df = overdue[od_cols].copy()
            od_df.columns = ["WO ID","Asset","Type","Actual Date","Scheduled","Overdue Days","Cost $"]
            od_df["Cost $"] = od_df["Cost $"].apply(lambda x: f"${x:,.0f}")
            od_df = od_df.sort_values("Overdue Days", ascending=False)
            st.dataframe(od_df, use_container_width=True, hide_index=True)
        else:
            st.success("No overdue work orders in the current period.")

    with tabs[2]:
        prevented = maint[maint["failure_prevented"] == 1]
        if not prevented.empty:
            p_cols = ["work_order_id","asset_name","maintenance_type",
                      "maintenance_date","actual_cost_usd","inspection_score","notes"]
            p_df = prevented[p_cols].copy()
            p_df.columns = ["WO ID","Asset","Type","Date","Cost $","Condition Score","Notes"]
            p_df["Cost $"] = p_df["Cost $"].apply(lambda x: f"${x:,.0f}")
            st.dataframe(p_df, use_container_width=True, hide_index=True)
            st.info(f"💡 {len(prevented)} PM/CBM interventions identified findings that prevented failures. "
                    f"Estimated avoided cost: ${prevented['actual_cost_usd'].sum() * 3:,.0f} "
                    f"(3× intervention cost — industry benchmark).")
