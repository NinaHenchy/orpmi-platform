"""
Page 1 — Operations Overview
Purpose: Executive-level facility health snapshot. Single-screen answer to
         "How is the facility performing right now?"
Audience: Operations Manager, Facility Manager, Executive Leadership
"""

import sys
from pathlib import Path
import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from dashboards.data_access import (
    get_latest_kpis, get_facility_summary, get_failures_by_asset,
    get_kpi_timeseries, get_monthly_kpis, get_failure_events
)
from dashboards.components.ui_components import (
    inject_css, page_header, section_header, alert_banner,
    apply_layout, THEME, CRITICALITY_COLORS, RISK_COLORS
)


def render_operations_overview():
    inject_css()
    page_header(
        "Operations Overview",
        "Offshore Production Complex OPC-Alpha · Facility Performance Dashboard · 2024",
        "🏠"
    )

    # ── DATA LOAD ────────────────────────────────────────────────────────
    summary = get_facility_summary()
    kpis    = get_latest_kpis()
    monthly = get_monthly_kpis()
    failures = get_failure_events()

    if kpis.empty or not summary:
        st.error("Database unavailable. Run `python scripts/setup_database.py` to initialise.")
        return

    # ── ALERT BANNER ─────────────────────────────────────────────────────
    high_risk = kpis[kpis["risk_level"].isin(["Critical", "High"])]
    if not high_risk.empty:
        names = ", ".join(high_risk["asset_name"].tolist())
        alert_banner(
            f"⚠ {len(high_risk)} asset(s) require attention: {names}. "
            f"Review maintenance priority scores and schedule inspections.",
            level="warning"
        )

    # ── TIER 1: FACILITY KPIs ─────────────────────────────────────────────
    section_header("Facility KPI Summary — Current Period")
    c1, c2, c3, c4, c5, c6 = st.columns(6)

    def avail_delta(v):
        t = 97.0
        d = round(v - t, 1)
        return f"{d:+.1f}% vs target"

    with c1:
        color = "normal" if summary["fleet_availability"] >= 97 else ("off" if summary["fleet_availability"] >= 93 else "inverse")
        st.metric("Fleet Availability", f"{summary['fleet_availability']}%",
                  avail_delta(summary["fleet_availability"]))
    with c2:
        st.metric("Fleet Health Score", f"{summary['fleet_health_score']}/100")
    with c3:
        st.metric("Avg MTBF", f"{int(summary['avg_mtbf'])} hrs",
                  help="Mean Time Between Failures — rolling 90-day across all assets")
    with c4:
        st.metric("Avg MTTR", f"{summary['avg_mttr']} hrs",
                  help="Mean Time To Repair — rolling 90-day")
    with c5:
        st.metric("Failures YTD", summary["total_failures_ytd"],
                  f"{summary['total_downtime_hrs_ytd']:.0f} hrs downtime")
    with c6:
        cost = summary["total_downtime_cost_usd"]
        st.metric("Downtime Cost YTD",
                  f"${cost/1e6:.2f}M" if cost >= 1e6 else f"${cost:,.0f}")

    st.markdown("<br>", unsafe_allow_html=True)

    # ── TIER 2: ASSET STATUS TABLE + FLEET AVAILABILITY CHART ────────────
    col_left, col_right = st.columns([1.1, 0.9])

    with col_left:
        section_header("Asset Status — Current Snapshot")

        # Build display table
        display = kpis[["asset_id","asset_name","criticality","availability_pct",
                         "health_score","reliability_score","mtbf_hrs","risk_level",
                         "maintenance_priority_score"]].copy()
        display.columns = ["ID","Asset","Criticality","Availability %",
                            "Health","Reliability","MTBF (hrs)","Risk","Priority Score"]
        display["Availability %"] = display["Availability %"].round(1)
        display["Health"] = display["Health"].round(1)
        display["Reliability"] = display["Reliability"].round(1)
        display["MTBF (hrs)"] = display["MTBF (hrs)"].round(0).astype(int)
        display["Priority Score"] = display["Priority Score"].round(1)

        def highlight_risk(row):
            risk = row["Risk"]
            color_map = {
                "Critical": "background-color:#1a0808;color:#ef4444",
                "High":     "background-color:#1a1500;color:#f59e0b",
                "Medium":   "background-color:#0f2040;color:#3b82f6",
                "Low":      "background-color:#0f2040;color:#00d4aa",
            }
            return [""] * (len(row) - 1) + [color_map.get(risk, "")]

        styled = display.style.apply(highlight_risk, axis=1).format({
            "Availability %": "{:.1f}",
            "Health": "{:.1f}",
            "Reliability": "{:.1f}",
        })
        st.dataframe(styled, use_container_width=True, hide_index=True, height=265)

    with col_right:
        section_header("Fleet Availability vs Target")

        # Gauge chart per asset
        fig_avail = go.Figure()
        asset_names_short = kpis["asset_id"].tolist()
        avail_vals = kpis["availability_pct"].tolist()
        target_val = 97.0

        colors = [THEME["green"] if v >= 97 else (THEME["amber"] if v >= 93 else THEME["red"])
                  for v in avail_vals]

        fig_avail.add_trace(go.Bar(
            x=asset_names_short,
            y=avail_vals,
            marker_color=colors,
            text=[f"{v:.1f}%" for v in avail_vals],
            textposition="outside",
            textfont=dict(size=11, color=THEME["text_primary"]),
            name="Availability",
        ))
        fig_avail.add_hline(
            y=target_val, line_dash="dash",
            line_color=THEME["amber"], line_width=1.5,
            annotation_text=f"Target {target_val}%",
            annotation_font=dict(color=THEME["amber"], size=10),
        )
        apply_layout(fig_avail, height=265)
        fig_avail.update_layout(
            yaxis=dict(range=[85, 101], title="Availability %"),
            showlegend=False,
            margin=dict(l=40, r=10, t=20, b=40),
        )
        st.plotly_chart(fig_avail, use_container_width=True, key="p1_operations_overview_chart_1")

    st.markdown("<br>", unsafe_allow_html=True)

    # ── TIER 3: MONTHLY TRENDS + FAILURE DISTRIBUTION ─────────────────────
    col_trend, col_fail = st.columns([1.2, 0.8])

    with col_trend:
        section_header("Fleet Availability Trend — Monthly")
        if not monthly.empty:
            monthly_fleet = monthly.groupby("year_month").agg(
                avg_availability=("avg_availability", "mean"),
                total_failures=("total_failures", "sum"),
                total_downtime=("total_downtime_hrs", "sum"),
            ).reset_index()

            fig_trend = make_subplots(specs=[[{"secondary_y": True}]])
            fig_trend.add_trace(go.Scatter(
                x=monthly_fleet["year_month"],
                y=monthly_fleet["avg_availability"],
                mode="lines+markers",
                name="Availability %",
                line=dict(color=THEME["blue"], width=2.5),
                marker=dict(size=7),
                fill="tozeroy",
                fillcolor="rgba(88,166,255,0.07)",
            ), secondary_y=False)
            fig_trend.add_trace(go.Bar(
                x=monthly_fleet["year_month"],
                y=monthly_fleet["total_failures"],
                name="Failures",
                marker_color=THEME["red"],
                opacity=0.6,
            ), secondary_y=True)
            fig_trend.add_hline(y=97.0, line_dash="dot", line_color=THEME["amber"],
                                line_width=1, secondary_y=False)
            apply_layout(fig_trend, height=280)
            fig_trend.update_layout(
                legend=dict(orientation="h", y=1.08, x=0, font=dict(size=10)),
                margin=dict(l=50, r=50, t=30, b=40),
            )
            fig_trend.update_yaxes(
                title_text="Availability %", range=[85, 102],
                secondary_y=False,
                tickfont=dict(size=10, color=THEME["text_secondary"]),
                gridcolor=THEME["grid_color"],
            )
            fig_trend.update_yaxes(
                title_text="Failure Count", secondary_y=True,
                tickfont=dict(size=10, color=THEME["red"]),
                showgrid=False,
            )
            st.plotly_chart(fig_trend, use_container_width=True, key="p1_operations_overview_chart_2")

    with col_fail:
        section_header("Failures by Asset — YTD")
        fail_by_asset = get_failures_by_asset()
        if not fail_by_asset.empty:
            fig_fail = go.Figure(go.Bar(
                x=fail_by_asset["total_failures"],
                y=fail_by_asset["asset_name"],
                orientation="h",
                marker_color=[THEME["asset_colors"].get(aid, THEME["blue"])
                              for aid in fail_by_asset["asset_id"]],
                text=fail_by_asset["total_failures"],
                textposition="outside",
                textfont=dict(size=11, color=THEME["text_primary"]),
            ))
            apply_layout(fig_fail, height=280)
            fig_fail.update_layout(
                xaxis_title="Failure Count",
                margin=dict(l=150, r=30, t=20, b=40),
                showlegend=False,
            )
            st.plotly_chart(fig_fail, use_container_width=True, key="p1_operations_overview_chart_3")

    st.markdown("<br>", unsafe_allow_html=True)

    # ── TIER 4: RISK MATRIX + MAINTENANCE COMPLIANCE ──────────────────────
    col_risk, col_comp = st.columns(2)

    with col_risk:
        section_header("Asset Risk Matrix — Criticality vs Health Score")
        fig_risk = go.Figure()

        for _, row in kpis.iterrows():
            color = RISK_COLORS.get(row["risk_level"], THEME["blue"])
            size = 20 + row["criticality_score"] * 6
            fig_risk.add_trace(go.Scatter(
                x=[row["criticality_score"]],
                y=[row["health_score"]],
                mode="markers+text",
                name=row["asset_id"],
                text=[row["asset_id"]],
                textposition="top center",
                textfont=dict(size=10, color=THEME["text_primary"]),
                marker=dict(
                    size=size, color=color,
                    opacity=0.85,
                    line=dict(color=THEME["border"], width=1.5),
                ),
                hovertemplate=(
                    f"<b>{row['asset_name']}</b><br>"
                    f"Criticality: {row['criticality']}<br>"
                    f"Health: {row['health_score']:.1f}<br>"
                    f"Risk: {row['risk_level']}<extra></extra>"
                ),
            ))

        # Quadrant shading
        fig_risk.add_shape(type="rect", x0=3.5, y0=0, x1=5.5, y1=65,
                           fillcolor="rgba(248,81,73,0.06)", line_width=0)
        fig_risk.add_shape(type="rect", x0=3.5, y0=65, x1=5.5, y1=101,
                           fillcolor="rgba(210,153,34,0.06)", line_width=0)

        apply_layout(fig_risk, height=300)
        fig_risk.update_layout(
            xaxis=dict(title="Criticality Score", range=[0.5, 5.8],
                       tickvals=[1,2,3,4,5],
                       ticktext=["Low","Medium","Medium","High","Critical"]),
            yaxis=dict(title="Health Score", range=[40, 105]),
            showlegend=False,
            margin=dict(l=50, r=20, t=20, b=50),
        )
        st.plotly_chart(fig_risk, use_container_width=True, key="p1_operations_overview_chart_4")

    with col_comp:
        section_header("Maintenance Compliance by Asset")
        comp_data = kpis[["asset_id", "asset_name", "maintenance_compliance_pct"]].sort_values(
            "maintenance_compliance_pct"
        )
        colors_comp = [
            THEME["green"] if v >= 90 else (THEME["amber"] if v >= 75 else THEME["red"])
            for v in comp_data["maintenance_compliance_pct"]
        ]
        fig_comp = go.Figure(go.Bar(
            x=comp_data["maintenance_compliance_pct"],
            y=comp_data["asset_name"],
            orientation="h",
            marker_color=colors_comp,
            text=[f"{v:.1f}%" for v in comp_data["maintenance_compliance_pct"]],
            textposition="outside",
            textfont=dict(size=11),
        ))
        fig_comp.add_vline(x=90, line_dash="dash", line_color=THEME["green"],
                           line_width=1.2,
                           annotation_text="Target 90%",
                           annotation_font=dict(size=9, color=THEME["green"]))
        apply_layout(fig_comp, height=300)
        fig_comp.update_layout(
            xaxis=dict(range=[0, 115], title="Compliance %"),
            showlegend=False,
            margin=dict(l=160, r=50, t=20, b=40),
        )
        st.plotly_chart(fig_comp, use_container_width=True, key="p1_operations_overview_chart_5")

    # ── TIER 5: FINANCIAL IMPACT TABLE ─────────────────────────────────────
    section_header("Financial Impact Summary — Downtime Cost Contribution by Asset")
    if not failures.empty:
        from config.settings import ASSET_REGISTRY
        fin_rows = []
        for asset_id, info in ASSET_REGISTRY.items():
            asset_failures = failures[failures["asset_id"] == asset_id]
            total_dt = asset_failures["downtime_hours"].sum() if not asset_failures.empty else 0
            total_cost = total_dt * info["downtime_cost_usd_per_hr"]
            fin_rows.append({
                "Asset": f"{asset_id} — {info['name']}",
                "Criticality": info["criticality"],
                "Failure Events": len(asset_failures),
                "Downtime hrs": round(total_dt, 1),
                "Cost Rate $/hr": f"${info['downtime_cost_usd_per_hr']:,}",
                "Downtime Cost $": f"${total_cost:,.0f}",
                "% of Total": "",
            })
        fin_df = pd.DataFrame(fin_rows)
        total_cost_all = sum(
            failures[failures["asset_id"] == aid]["downtime_hours"].sum()
            * ASSET_REGISTRY[aid]["downtime_cost_usd_per_hr"]
            for aid in ASSET_REGISTRY
        )
        fin_df["% of Total"] = fin_df.apply(lambda r: (
            f"{float(r['Downtime Cost $'].replace('$','').replace(',','')) / max(total_cost_all, 1) * 100:.1f}%"
            if r["Downtime hrs"] > 0 else "0.0%"
        ), axis=1)

        st.dataframe(fin_df, use_container_width=True, hide_index=True)

        total_row_html = f"""
        <div class="orpmi-card" style="border-color:#3b82f6;margin-top:4px;">
            <span style="color:#4d6a85;font-size:11px;text-transform:uppercase;">Total Facility Downtime Cost YTD</span>
            <span style="color:#ef4444;font-size:20px;font-weight:700;margin-left:20px;">
                ${total_cost_all:,.0f}
            </span>
            <span style="color:#4d6a85;font-size:12px;margin-left:12px;">
                ({failures['downtime_hours'].sum():.1f} total downtime hours)
            </span>
        </div>
        """
        st.markdown(total_row_html, unsafe_allow_html=True)
