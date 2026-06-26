"""
Page 6 — Sensor Trends
Purpose: Time-series sensor data with ISO 10816 vibration zones, temperature & pressure trending.
Audience: Reliability Engineer, Process Engineer, Maintenance Technician
"""

import sys
from pathlib import Path
import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from dashboards.data_access import get_operating_data, get_assets, get_failure_events
from dashboards.components.ui_components import (
    inject_css, page_header, section_header, apply_layout, THEME
)
from config.settings import ASSET_REGISTRY


def render_sensor_trends():
    inject_css()
    page_header(
        "Sensor Trends",
        "Vibration · Temperature · Pressure · Flow · Efficiency — Time-Series Analysis",
        "🌡️"
    )

    # ── ASSET SELECTOR ────────────────────────────────────────────────────
    col_sel1, col_sel2 = st.columns([1, 2])
    with col_sel1:
        asset_options = list(ASSET_REGISTRY.keys())
        selected_asset = st.selectbox(
            "Select Asset",
            options=asset_options,
            format_func=lambda x: f"{x} — {ASSET_REGISTRY[x]['name']}",
            index=2,  # Default to C-201 (most interesting)
        )
    with col_sel2:
        date_range = st.select_slider(
            "Date Range",
            options=["Jan–Mar", "Apr–Jun", "Jul–Sep", "Oct–Dec", "Full Year"],
            value="Full Year",
        )

    date_map = {
        "Jan–Mar": ("2024-01-01", "2024-03-31"),
        "Apr–Jun": ("2024-04-01", "2024-06-30"),
        "Jul–Sep": ("2024-07-01", "2024-09-30"),
        "Oct–Dec": ("2024-10-01", "2024-12-31"),
        "Full Year": ("2024-01-01", "2024-12-31"),
    }
    start_d, end_d = date_map[date_range]

    ops_data = get_operating_data(selected_asset, start_d, end_d)
    failures = get_failure_events([selected_asset])
    asset_info = ASSET_REGISTRY[selected_asset]

    if ops_data.empty:
        st.warning(f"No operating data for {selected_asset}.")
        return

    ops_data["record_date"] = pd.to_datetime(ops_data["record_date"])

    # ── ASSET SPECS ───────────────────────────────────────────────────────
    col_s1, col_s2, col_s3, col_s4 = st.columns(4)
    with col_s1: st.metric("Asset", selected_asset)
    with col_s2: st.metric("Design Pressure", f"{asset_info['design_pressure_bar']} bar")
    with col_s3: st.metric("Design Temp", f"{asset_info['design_temp_c']} °C")
    with col_s4:
        avg_eff = ops_data["efficiency_pct"].dropna().mean()
        st.metric("Avg Efficiency", f"{avg_eff:.1f}%")

    st.markdown("<br>", unsafe_allow_html=True)

    # ── VIBRATION TREND (ISO 10816) ────────────────────────────────────────
    section_header(f"Vibration Trend — {selected_asset} (ISO 10816 Severity Zones)")

    vib_data = ops_data.dropna(subset=["vibration_mm_s"])
    fig_vib = go.Figure()

    # Zone shading (ISO 10816)
    zones = [
        (0, 2.3, "rgba(63,185,80,0.08)", "Zone A — Normal"),
        (2.3, 4.5, "rgba(88,166,255,0.08)", "Zone B — Acceptable"),
        (4.5, 7.1, "rgba(210,153,34,0.12)", "Zone C — Alarm"),
        (7.1, 12, "rgba(248,81,73,0.12)", "Zone D — Shutdown"),
    ]
    for y0, y1, color, label in zones:
        fig_vib.add_hrect(y0=y0, y1=y1, fillcolor=color, line_width=0,
                          annotation_text=label,
                          annotation_position="right",
                          annotation_font=dict(size=8, color=THEME["text_muted"]))

    # Colour-code points by zone
    colors_vib = []
    for v in vib_data["vibration_mm_s"]:
        if v >= 7.1: colors_vib.append(THEME["red"])
        elif v >= 4.5: colors_vib.append(THEME["amber"])
        elif v >= 2.3: colors_vib.append(THEME["blue"])
        else: colors_vib.append(THEME["green"])

    fig_vib.add_trace(go.Scatter(
        x=vib_data["record_date"],
        y=vib_data["vibration_mm_s"],
        mode="lines+markers",
        name="Vibration mm/s",
        line=dict(color=THEME["blue"], width=1.5),
        marker=dict(size=4, color=colors_vib),
        hovertemplate="Date: %{x|%d %b}<br>Vibration: %{y:.3f} mm/s<extra></extra>",
    ))

    # Mark failure dates
    if not failures.empty:
        fail_dates = pd.to_datetime(failures["failure_date"])
        for fd in fail_dates:
            fig_vib.add_vline(x=fd, line_dash="dot", line_color=THEME["red"],
                              line_width=1.5,
                              annotation_text="⚠ Failure",
                              annotation_font=dict(size=8, color=THEME["red"]))

    apply_layout(fig_vib, height=280)
    fig_vib.update_layout(
        yaxis=dict(title="Vibration (mm/s)", range=[0, max(vib_data["vibration_mm_s"].max() * 1.2, 8)]),
        showlegend=False,
        margin=dict(l=50, r=120, t=20, b=50),
    )
    st.plotly_chart(fig_vib, use_container_width=True, key="p6_sensor_trends_chart_1")

    # ── TEMPERATURE & PRESSURE ─────────────────────────────────────────────
    section_header(f"Temperature & Pressure Trends — {selected_asset}")
    col_temp, col_pres = st.columns(2)

    with col_temp:
        temp_data = ops_data.dropna(subset=["operating_temp_c"])
        design_temp = asset_info["design_temp_c"]
        fig_temp = go.Figure()
        fig_temp.add_trace(go.Scatter(
            x=temp_data["record_date"],
            y=temp_data["operating_temp_c"],
            mode="lines",
            name="Operating Temp",
            line=dict(color=THEME["orange"], width=1.8),
            fill="tozeroy",
            fillcolor="rgba(240,136,62,0.06)",
        ))
        fig_temp.add_hline(y=design_temp, line_dash="dash",
                           line_color=THEME["red"], line_width=1.5,
                           annotation_text=f"Design Max {design_temp}°C",
                           annotation_font=dict(size=9, color=THEME["red"]))
        apply_layout(fig_temp, "Temperature (°C)", height=260)
        fig_temp.update_layout(showlegend=False, margin=dict(l=50, r=60, t=30, b=50))
        st.plotly_chart(fig_temp, use_container_width=True, key="p6_sensor_trends_chart_2")

    with col_pres:
        pres_data = ops_data.dropna(subset=["operating_pressure_bar"])
        design_pres = asset_info["design_pressure_bar"]
        pres_colors = [THEME["red"] if v > design_pres * 0.95 else THEME["cyan"]
                       for v in pres_data["operating_pressure_bar"]]
        fig_pres = go.Figure()
        fig_pres.add_trace(go.Scatter(
            x=pres_data["record_date"],
            y=pres_data["operating_pressure_bar"],
            mode="lines",
            name="Pressure",
            line=dict(color=THEME["cyan"], width=1.8),
            fill="tozeroy",
            fillcolor="rgba(57,211,242,0.06)",
        ))
        fig_pres.add_hline(y=design_pres * 0.90, line_dash="dash",
                           line_color=THEME["amber"], line_width=1,
                           annotation_text=f"90% Design {design_pres*0.9:.0f} bar",
                           annotation_font=dict(size=9, color=THEME["amber"]))
        apply_layout(fig_pres, "Pressure (bar)", height=260)
        fig_pres.update_layout(showlegend=False, margin=dict(l=50, r=80, t=30, b=50))
        st.plotly_chart(fig_pres, use_container_width=True, key="p6_sensor_trends_chart_3")

    # ── EFFICIENCY DEGRADATION ─────────────────────────────────────────────
    section_header(f"Efficiency Degradation Trend — {selected_asset}")
    eff_data = ops_data[ops_data["is_running"] == 1].dropna(subset=["efficiency_pct"])

    if len(eff_data) > 10:
        # Add trend line
        x_numeric = np.arange(len(eff_data))
        z = np.polyfit(x_numeric, eff_data["efficiency_pct"], 1)
        p = np.poly1d(z)
        trend_y = p(x_numeric)
        monthly_decline = z[0] * 30
        annual_decline = z[0] * 365

        fig_eff = go.Figure()
        fig_eff.add_trace(go.Scatter(
            x=eff_data["record_date"],
            y=eff_data["efficiency_pct"],
            mode="lines",
            name="Efficiency %",
            line=dict(color=THEME["green"], width=1.5),
            fill="tozeroy",
            fillcolor="rgba(63,185,80,0.06)",
        ))
        fig_eff.add_trace(go.Scatter(
            x=eff_data["record_date"],
            y=trend_y,
            mode="lines",
            name=f"Trend ({annual_decline:+.1f}%/yr)",
            line=dict(color=THEME["amber"], width=2, dash="dot"),
        ))
        apply_layout(fig_eff, height=260)
        fig_eff.update_layout(
            yaxis=dict(title="Efficiency %", range=[max(0, eff_data["efficiency_pct"].min() - 5), 105]),
            legend=dict(orientation="h", y=1.08, x=0),
            margin=dict(l=50, r=20, t=35, b=50),
        )
        st.plotly_chart(fig_eff, use_container_width=True, key="p6_sensor_trends_chart_4")

        col_e1, col_e2, col_e3 = st.columns(3)
        with col_e1: st.metric("Current Efficiency", f"{eff_data['efficiency_pct'].iloc[-1]:.1f}%")
        with col_e2: st.metric("Monthly Decline", f"{monthly_decline:+.2f}%/month")
        with col_e3: st.metric("Annual Projection", f"{annual_decline:+.1f}%/year")

    # ── MULTI-PARAMETER CORRELATION ────────────────────────────────────────
    section_header(f"Operating Parameter Summary — {selected_asset} Statistics")
    if not ops_data.empty:
        numeric_cols = ["vibration_mm_s", "operating_temp_c", "operating_pressure_bar",
                        "efficiency_pct", "power_consumption_kw"]
        stats_rows = []
        for col in numeric_cols:
            data_col = ops_data[col].dropna()
            if len(data_col) == 0:
                continue
            label_map = {
                "vibration_mm_s": "Vibration (mm/s)",
                "operating_temp_c": "Temperature (°C)",
                "operating_pressure_bar": "Pressure (bar)",
                "efficiency_pct": "Efficiency (%)",
                "power_consumption_kw": "Power (kW)",
            }
            stats_rows.append({
                "Parameter": label_map.get(col, col),
                "Min": round(data_col.min(), 2),
                "Max": round(data_col.max(), 2),
                "Mean": round(data_col.mean(), 2),
                "Std Dev": round(data_col.std(), 3),
                "P95": round(data_col.quantile(0.95), 2),
                "Readings": len(data_col),
            })
        if stats_rows:
            st.dataframe(pd.DataFrame(stats_rows), use_container_width=True, hide_index=True)
