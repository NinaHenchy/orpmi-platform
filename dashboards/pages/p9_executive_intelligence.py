"""
Page 9 — Executive Operations Intelligence
Purpose: C-suite summary — AI narrative, financial impact, fleet scorecard, risk register.
Audience: Operations Director, VP Operations, Executive Leadership
"""

import sys
from pathlib import Path
import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from models.risk_scoring_engine import get_ai_narrative, score_all_assets, load_model_metadata
from dashboards.data_access import (
    get_latest_kpis, get_facility_summary, get_failure_events,
    get_maintenance_records, get_monthly_kpis
)
from dashboards.components.ui_components import (
    inject_css, page_header, section_header, alert_banner, apply_layout,
    THEME, RISK_COLORS, CRITICALITY_COLORS
)
from config.settings import ASSET_REGISTRY, FACILITY_NAME, FACILITY_CODE


def render_executive_intelligence():
    inject_css()
    page_header(
        "Executive Operations Intelligence",
        f"{FACILITY_NAME} · {FACILITY_CODE} · Operations & Reliability Report · 2024",
        "🎯"
    )

    kpis      = get_latest_kpis()
    summary   = get_facility_summary()
    failures  = get_failure_events()
    maint     = get_maintenance_records()
    monthly   = get_monthly_kpis()
    scores    = score_all_assets()
    narratives = get_ai_narrative()
    metadata   = load_model_metadata()

    if kpis.empty or not summary:
        st.error("Data unavailable.")
        return

    # ── EXECUTIVE HEADLINE METRICS ─────────────────────────────────────────
    section_header("Facility Performance — Executive KPI Summary")

    total_dt_cost = summary["total_downtime_cost_usd"]
    total_maint_cost = summary["total_maintenance_cost_usd"]
    fleet_avail = summary["fleet_availability"]
    fleet_health = summary["fleet_health_score"]

    # RAG scoring
    avail_rag  = "🟢" if fleet_avail >= 97 else ("🟡" if fleet_avail >= 93 else "🔴")
    health_rag = "🟢" if fleet_health >= 80 else ("🟡" if fleet_health >= 65 else "🔴")

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Fleet Availability", f"{avail_rag} {fleet_avail}%",
                  f"Target: 97.0% | {'▲ Above' if fleet_avail>=97 else '▼ Below'} target")
    with c2:
        st.metric("Fleet Health Score", f"{health_rag} {fleet_health}/100")
    with c3:
        st.metric("Total Downtime Cost YTD",
                  f"${total_dt_cost/1e6:.2f}M" if total_dt_cost >= 1e6 else f"${total_dt_cost:,.0f}",
                  f"{summary['total_downtime_hrs_ytd']:.0f} hrs unplanned downtime")
    with c4:
        st.metric("Maintenance Spend YTD",
                  f"${total_maint_cost/1e6:.2f}M" if total_maint_cost >= 1e6 else f"${total_maint_cost:,.0f}",
                  f"Compliance: {summary['maintenance_compliance']:.1f}%")

    st.markdown("<br>", unsafe_allow_html=True)
    c5, c6, c7, c8 = st.columns(4)
    with c5:
        st.metric("Fleet Reliability", f"{kpis['reliability_score'].mean():.1f}/100")
    with c6:
        st.metric("Avg MTBF", f"{int(summary['avg_mtbf'])} hrs",
                  f"{summary['avg_mtbf']/24:.1f} days between failures")
    with c7:
        st.metric("Failures YTD", summary["total_failures_ytd"])
    with c8:
        high_risk = len(scores[scores["risk_level_ml"].isin(["Critical","High"])])
        st.metric("Assets at Elevated Risk", high_risk,
                  help="Assets with >40% 30-day failure probability")

    st.markdown("<br>", unsafe_allow_html=True)

    # ── FLEET PERFORMANCE RADAR ────────────────────────────────────────────
    col_radar, col_risk_summary = st.columns(2)

    with col_radar:
        section_header("Fleet Performance Radar")
        categories  = ["Availability", "Health Score", "Reliability",
                        "PM Compliance", "MTBF Index", "Safety Margin"]
        avail_norm  = min(fleet_avail / 100 * 100, 100)
        health_norm = fleet_health
        reli_norm   = kpis["reliability_score"].mean()
        comp_norm   = summary["maintenance_compliance"]
        mtbf_norm   = min(summary["avg_mtbf"] / 1000 * 100, 100)
        safety_norm = max(0, 100 - scores["failure_probability_30d"].mean() * 100)

        vals = [avail_norm, health_norm, reli_norm, comp_norm, mtbf_norm, safety_norm]
        vals_closed = vals + [vals[0]]
        cats_closed = categories + [categories[0]]

        fig_radar = go.Figure()
        # Target zone (97% equivalent on each axis)
        target_vals = [97, 85, 87, 90, 80, 90]
        fig_radar.add_trace(go.Scatterpolar(
            r=target_vals + [target_vals[0]],
            theta=cats_closed,
            fill="toself",
            fillcolor="rgba(63,185,80,0.08)",
            line=dict(color=THEME["green"], width=1, dash="dash"),
            name="Target",
        ))
        fig_radar.add_trace(go.Scatterpolar(
            r=vals_closed,
            theta=cats_closed,
            fill="toself",
            fillcolor="rgba(88,166,255,0.15)",
            line=dict(color=THEME["blue"], width=2.5),
            name="Actual",
            marker=dict(size=7),
        ))
        fig_radar.update_layout(
            polar=dict(
                radialaxis=dict(visible=True, range=[0, 110],
                                tickfont=dict(size=9, color=THEME["text_muted"]),
                                gridcolor=THEME["grid_color"],
                                linecolor=THEME["grid_color"]),
                angularaxis=dict(tickfont=dict(size=10, color=THEME["text_secondary"]),
                                 linecolor=THEME["border"]),
                bgcolor=THEME["bg_secondary"],
            ),
            paper_bgcolor=THEME["plotly_paper"],
            font=dict(color=THEME["text_primary"]),
            height=330,
            showlegend=True,
            legend=dict(orientation="h", y=-0.12, x=0.2, font=dict(size=10)),
            margin=dict(l=40, r=40, t=20, b=60),
        )
        st.plotly_chart(fig_radar, use_container_width=True, key="p9_executive_intelligence_chart_1")

    with col_risk_summary:
        section_header("Asset Risk Register — Current Status")
        scores_display = scores.merge(
            kpis[["asset_id","availability_pct","health_score","mtbf_hrs"]],
            on="asset_id", how="left"
        )

        for _, row in scores_display.iterrows():
            risk  = row.get("risk_level_ml","Low")
            color = RISK_COLORS.get(risk, THEME["blue"])
            prob  = float(row.get("failure_probability_30d", 0))
            avail = float(row.get("availability_pct", 0))
            health = float(row.get("health_score", 0))

            st.markdown(f"""
            <div style="background:#0f2040;border:1px solid {color}44;border-left:3px solid {color};
                         border-radius:6px;padding:10px 14px;margin-bottom:6px;">
                <div style="display:flex;justify-content:space-between;align-items:center;">
                    <div>
                        <span style="font-size:13px;font-weight:700;color:#e8edf5;">{row['asset_id']}</span>
                        <span style="font-size:11px;color:#4d6a85;margin-left:6px;">{row.get('asset_name','')}</span>
                    </div>
                    <div style="display:flex;gap:16px;align-items:center;">
                        <span style="font-size:11px;color:#4d6a85;">Avail: {avail:.1f}%</span>
                        <span style="font-size:11px;color:#4d6a85;">Health: {health:.0f}</span>
                        <span style="font-size:12px;font-weight:600;padding:2px 9px;border-radius:3px;
                               color:{color};background:{color}22;border:1px solid {color}44;">
                            {risk} · {prob*100:.0f}%
                        </span>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── AI OPERATIONS NARRATIVES ───────────────────────────────────────────
    section_header("AI Operations Intelligence — Asset Status Narratives")
    st.caption(
        "Narratives generated by the ORPMI predictive model combining failure probability, "
        "historical performance, and operational KPIs. Review during daily management briefings."
    )

    for asset_id, narr in narratives.items():
        risk   = narr["risk_level"]
        color  = RISK_COLORS.get(risk, THEME["blue"])
        border = "border-left:4px solid " + color

        st.markdown(f"""
        <div style="background:#0f2040;border:1px solid {color}33;{border};
                     border-radius:8px;padding:14px 18px;margin-bottom:12px;">
            <div style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:8px;margin-bottom:8px;">
                <div>
                    <span style="font-size:14px;font-weight:700;color:#e8edf5;">{asset_id} — {narr['asset_name']}</span>
                    <span style="font-size:10px;margin-left:10px;padding:2px 8px;border-radius:3px;
                           color:{color};background:{color}22;border:1px solid {color}44;font-weight:600;">
                        {risk} RISK · {narr['failure_probability']*100:.0f}%
                    </span>
                </div>
                <div style="display:flex;gap:20px;">
                    <div style="text-align:center;">
                        <div style="font-size:9px;color:#4d6a85;text-transform:uppercase;">Failures YTD</div>
                        <div style="font-size:16px;font-weight:600;color:#e8edf5;">{narr['failure_count_ytd']}</div>
                    </div>
                    <div style="text-align:center;">
                        <div style="font-size:9px;color:#4d6a85;text-transform:uppercase;">Downtime hrs</div>
                        <div style="font-size:16px;font-weight:600;color:#e8edf5;">{narr['downtime_hrs_ytd']:.1f}</div>
                    </div>
                    <div style="text-align:center;">
                        <div style="font-size:9px;color:#4d6a85;text-transform:uppercase;">Downtime Cost</div>
                        <div style="font-size:16px;font-weight:600;color:#ef4444;">${narr['downtime_cost_ytd']:,.0f}</div>
                    </div>
                </div>
            </div>
            <p style="font-size:12px;color:#8aa3be;line-height:1.6;margin:0;">{narr['narrative']}</p>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── YTD FINANCIAL SUMMARY ──────────────────────────────────────────────
    section_header("YTD Financial Performance — Cost Summary")
    col_fin1, col_fin2 = st.columns(2)

    with col_fin1:
        # Monthly cost stack
        if not monthly.empty:
            monthly_agg = monthly.groupby("year_month").agg(
                maint_cost=("total_maint_cost","sum"),
            ).reset_index()

            if not failures.empty:
                fail_month = failures.copy()
                fail_month["month"] = pd.to_datetime(fail_month["failure_date"]).dt.strftime("%Y-%m")
                fail_cost = fail_month.groupby("month")["financial_impact_usd"].sum().reset_index()
                fail_cost.columns = ["year_month","dt_cost"]
                monthly_agg = monthly_agg.merge(fail_cost, on="year_month", how="left").fillna(0)
            else:
                monthly_agg["dt_cost"] = 0

            fig_cost = go.Figure()
            fig_cost.add_trace(go.Bar(
                x=monthly_agg["year_month"],
                y=monthly_agg["maint_cost"],
                name="Maintenance Cost",
                marker_color=THEME["blue"],
                opacity=0.8,
            ))
            fig_cost.add_trace(go.Bar(
                x=monthly_agg["year_month"],
                y=monthly_agg["dt_cost"],
                name="Downtime Cost",
                marker_color=THEME["red"],
                opacity=0.8,
            ))
            apply_layout(fig_cost, "Monthly Cost Stack (USD)", height=300)
            fig_cost.update_layout(
                barmode="stack",
                yaxis_title="Cost (USD)",
                legend=dict(orientation="h", y=1.1, x=0, font=dict(size=10)),
                margin=dict(l=60, r=20, t=35, b=60),
            )
            st.plotly_chart(fig_cost, use_container_width=True, key="p9_executive_intelligence_chart_2")

    with col_fin2:
        # Cost breakdown donut
        labels_cost = ["Downtime Cost", "Maintenance Cost"]
        values_cost = [total_dt_cost, total_maint_cost]
        fig_donut = go.Figure(go.Pie(
            labels=labels_cost,
            values=values_cost,
            hole=0.55,
            marker_colors=[THEME["red"], THEME["blue"]],
            textinfo="label+percent",
            textfont=dict(size=11),
        ))
        fig_donut.add_annotation(
            text=f"Total<br>${(total_dt_cost+total_maint_cost)/1e3:.0f}K",
            x=0.5, y=0.5,
            font=dict(size=14, color=THEME["text_primary"]),
            showarrow=False,
        )
        apply_layout(fig_donut, "Total Cost Breakdown YTD", height=300)
        fig_donut.update_layout(
            showlegend=True,
            legend=dict(orientation="h", y=-0.12, x=0.15),
            margin=dict(l=20, r=20, t=35, b=60),
        )
        st.plotly_chart(fig_donut, use_container_width=True, key="p9_executive_intelligence_chart_3")

    st.markdown("<br>", unsafe_allow_html=True)

    # ── MODEL PERFORMANCE SUMMARY ──────────────────────────────────────────
    if metadata:
        section_header("Predictive Model Performance Summary")
        champion = metadata.get("champion_model","RF")
        roc      = metadata.get("champion_test_roc_auc",0)

        st.markdown(f"""
        <div class="orpmi-card" style="border-color:#3b82f6;">
            <div style="display:flex;justify-content:space-between;flex-wrap:wrap;gap:12px;align-items:center;">
                <div>
                    <div class="orpmi-card-header">Predictive Maintenance Model</div>
                    <div style="font-size:15px;font-weight:700;color:#e8edf5;margin-top:4px;">
                        {champion} — Calibrated Failure Probability Model
                    </div>
                    <div style="font-size:12px;color:#4d6a85;margin-top:4px;">
                        {metadata.get('feature_count',0)} engineered features ·
                        Trained on {metadata.get('training_rows',0):,} daily records ·
                        Temporal validation (Oct–Dec 2024 test set)
                    </div>
                </div>
                <div style="display:flex;gap:24px;">
                    <div style="text-align:center;">
                        <div style="font-size:9px;color:#4d6a85;text-transform:uppercase;">ROC-AUC</div>
                        <div style="font-size:22px;font-weight:700;color:#00d4aa;">{roc:.4f}</div>
                        <div style="font-size:9px;color:#4d6a85;">Excellent ≥0.85</div>
                    </div>
                    <div style="text-align:center;">
                        <div style="font-size:9px;color:#4d6a85;text-transform:uppercase;">Recall</div>
                        <div style="font-size:22px;font-weight:700;color:#3b82f6;">{metadata.get('champion_recall',0):.3f}</div>
                        <div style="font-size:9px;color:#4d6a85;">Failure capture rate</div>
                    </div>
                    <div style="text-align:center;">
                        <div style="font-size:9px;color:#4d6a85;text-transform:uppercase;">F1</div>
                        <div style="font-size:22px;font-weight:700;color:#3b82f6;">{metadata.get('champion_f1',0):.3f}</div>
                    </div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
