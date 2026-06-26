"""
Page 10 — ORPMI Data Entry
Log real operational data — saved permanently to the database.
"""

import sys
from pathlib import Path
_root = Path(__file__).resolve().parent.parent.parent
for _p in [str(_root), "/app"]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

import streamlit as st
import pandas as pd
from datetime import date, datetime
from sqlalchemy import text

from dashboards.components.ui_components import (
    inject_css, page_header, section_header, THEME
)
from config.settings import ASSET_REGISTRY, FAILURE_CATEGORIES, MAINTENANCE_TYPES


def get_engine():
    from database.db_connection import get_engine as _get
    return _get()


def render_data_entry():
    inject_css()
    page_header(
        "Data Entry",
        "Log real operational data — saved permanently to the database",
        "➕"
    )

    st.info(
        "All entries are saved directly to the database and immediately "
        "reflected across all dashboard pages."
    )

    tab1, tab2, tab3, tab4 = st.tabs([
        "⚠️ Failure Event",
        "🔧 Maintenance Record",
        "🔍 Inspection Record",
        "📊 Operating Data",
    ])

    # ── TAB 1: FAILURE EVENT ──────────────────────────────────────────
    with tab1:
        section_header("Log New Failure Event")
        with st.form("failure_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                asset_id = st.selectbox(
                    "Asset *", options=list(ASSET_REGISTRY.keys()),
                    format_func=lambda x: f"{x} — {ASSET_REGISTRY[x]['name']}"
                )
                failure_date = st.date_input("Failure Date *", value=date.today())
                failure_time = st.time_input("Failure Time *")
                failure_category = st.selectbox("Failure Category *", FAILURE_CATEGORIES)
                severity = st.selectbox("Severity *", ["Critical","Major","Minor","Negligible"])
            with col2:
                downtime_hours = st.number_input("Downtime Hours *", min_value=0.0, max_value=720.0, value=4.0, step=0.5)
                time_to_repair = st.number_input("Time to Repair (hrs)", min_value=0.0, max_value=720.0, value=3.0, step=0.5)
                detection_method = st.selectbox("Detection Method", [
                    "Operator Report","DCS Alarm","Condition Monitoring Round",
                    "Vibration Survey","Routine Inspection","SCADA Alert","Other"
                ])
                reported_by = st.text_input("Reported By")
                is_recurrence = st.checkbox("Recurring failure?")

            description = st.text_area("Failure Description *", placeholder="What happened, where, and what was the immediate impact...")
            root_cause = st.text_area("Root Cause", placeholder="What caused the failure?")
            corrective_action = st.text_area("Corrective Action Taken", placeholder="What was done to restore the equipment?")

            if st.form_submit_button("💾 Save Failure Event", use_container_width=True, type="primary"):
                if not description:
                    st.error("Please provide a failure description.")
                else:
                    try:
                        engine = get_engine()
                        asset_info = ASSET_REGISTRY[asset_id]
                        financial_impact = round(downtime_hours * asset_info["downtime_cost_usd_per_hr"], 0)
                        wo_id = f"WO-{asset_id}-{failure_date.strftime('%Y%m%d')}-{datetime.now().strftime('%H%M%S')}"
                        with engine.connect() as conn:
                            conn.execute(text("""
                                INSERT INTO failure_events (
                                    asset_id, failure_date, failure_time,
                                    failure_category, failure_description,
                                    failure_severity, detection_method,
                                    downtime_hours, time_to_repair_hrs,
                                    production_loss_bbls, financial_impact_usd,
                                    root_cause, corrective_action,
                                    is_recurrence, work_order_id, reported_by
                                ) VALUES (
                                    :asset_id, :failure_date, :failure_time,
                                    :category, :description, :severity, :detection,
                                    :downtime, :ttr, :prod_loss, :financial,
                                    :root_cause, :corrective, :recurrence, :wo_id, :reported_by
                                )
                            """), {
                                "asset_id": asset_id, "failure_date": str(failure_date),
                                "failure_time": str(failure_time), "category": failure_category,
                                "description": description, "severity": severity,
                                "detection": detection_method, "downtime": downtime_hours,
                                "ttr": time_to_repair, "prod_loss": round((downtime_hours/24)*45000*0.15, 1),
                                "financial": financial_impact, "root_cause": root_cause,
                                "corrective": corrective_action, "recurrence": int(is_recurrence),
                                "wo_id": wo_id, "reported_by": reported_by,
                            })
                            conn.commit()
                        st.success(f"✅ Failure event saved! Work Order: {wo_id} | Financial Impact: ${financial_impact:,.0f}")
                    except Exception as e:
                        st.error(f"Error saving record: {e}")

    # ── TAB 2: MAINTENANCE ────────────────────────────────────────────
    with tab2:
        section_header("Log New Maintenance Record")
        with st.form("maintenance_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                m_asset = st.selectbox("Asset *", options=list(ASSET_REGISTRY.keys()),
                    format_func=lambda x: f"{x} — {ASSET_REGISTRY[x]['name']}", key="m_asset")
                m_type = st.selectbox("Maintenance Type *", MAINTENANCE_TYPES)
                m_date = st.date_input("Maintenance Date *", value=date.today(), key="m_date")
                scheduled_date = st.date_input("Scheduled Date", value=date.today(), key="s_date")
                technician = st.text_input("Technician")
            with col2:
                duration_hrs = st.number_input("Duration (hrs) *", min_value=0.5, max_value=240.0, value=4.0, step=0.5)
                actual_cost = st.number_input("Actual Cost (USD) *", min_value=0.0, max_value=5000000.0, value=5000.0, step=100.0)
                inspection_score = st.slider("Post-Maintenance Condition Score", 0, 100, 85)
                is_compliant = st.checkbox("Completed on schedule?", value=True)
                failure_prevented = st.checkbox("Did this PM prevent a potential failure?")

            m_description = st.text_area("Maintenance Description *", placeholder="What maintenance work was performed?")

            if st.form_submit_button("💾 Save Maintenance Record", use_container_width=True, type="primary"):
                if not m_description:
                    st.error("Please provide a maintenance description.")
                else:
                    try:
                        engine = get_engine()
                        wo_id = f"WO-{m_asset}-{m_date.strftime('%Y%m%d')}-{datetime.now().strftime('%H%M%S')}"
                        with engine.connect() as conn:
                            conn.execute(text("""
                                INSERT INTO maintenance_records (
                                    asset_id, work_order_id, maintenance_type,
                                    maintenance_date, scheduled_date,
                                    maintenance_description, technician,
                                    duration_hrs, actual_cost_usd, estimated_cost_usd,
                                    compliance_flag, overdue_days,
                                    failure_prevented, inspection_score
                                ) VALUES (
                                    :asset_id, :wo_id, :m_type, :m_date, :s_date,
                                    :description, :tech, :duration, :actual_cost, :est_cost,
                                    :compliant, :overdue, :prevented, :score
                                )
                            """), {
                                "asset_id": m_asset, "wo_id": wo_id, "m_type": m_type,
                                "m_date": str(m_date), "s_date": str(scheduled_date),
                                "description": m_description, "tech": technician,
                                "duration": duration_hrs, "actual_cost": actual_cost,
                                "est_cost": actual_cost * 0.9,
                                "compliant": int(is_compliant),
                                "overdue": max(0, (m_date - scheduled_date).days) if not is_compliant else 0,
                                "prevented": int(failure_prevented), "score": inspection_score,
                            })
                            conn.commit()
                        st.success(f"✅ Maintenance record saved! Work Order: {wo_id} | Cost: ${actual_cost:,.0f}")
                    except Exception as e:
                        st.error(f"Error saving record: {e}")

    # ── TAB 3: INSPECTION ─────────────────────────────────────────────
    with tab3:
        section_header("Log New Inspection Record")
        with st.form("inspection_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                i_asset = st.selectbox("Asset *", options=list(ASSET_REGISTRY.keys()),
                    format_func=lambda x: f"{x} — {ASSET_REGISTRY[x]['name']}", key="i_asset")
                i_date = st.date_input("Inspection Date *", value=date.today(), key="i_date")
                i_type = st.selectbox("Inspection Type *", [
                    "Routine Inspection","NDT Survey","Vibration Survey",
                    "Thermographic Survey","Corrosion Survey","Regulatory Inspection"
                ])
                inspector = st.text_input("Inspector Name")
            with col2:
                i_score = st.slider("Inspection Score *", 0, 100, 80)
                condition = st.selectbox("Overall Condition *", ["Excellent","Good","Fair","Poor","Critical"])
                findings_count = st.number_input("Number of Findings", min_value=0, max_value=50, value=0)
                critical_findings = st.number_input("Critical Findings", min_value=0, max_value=10, value=0)
                corrosion_rate = st.number_input("Corrosion Rate (mm/yr)", min_value=0.0, max_value=5.0, value=0.1, step=0.01)

            i_notes = st.text_area("Inspection Notes", placeholder="Summary of findings and observations...")

            if st.form_submit_button("💾 Save Inspection Record", use_container_width=True, type="primary"):
                try:
                    engine = get_engine()
                    insp_ref = f"INSP-{i_asset}-{i_date.strftime('%Y%m')}-{datetime.now().strftime('%H%M%S')}"
                    with engine.connect() as conn:
                        conn.execute(text("""
                            INSERT INTO inspection_records (
                                asset_id, inspection_date, inspection_type,
                                inspector_name, inspection_score, overall_condition,
                                findings_count, critical_findings,
                                corrosion_rate_mm_yr, action_required,
                                action_description, report_reference
                            ) VALUES (
                                :asset_id, :i_date, :i_type, :inspector, :score,
                                :condition, :findings, :critical, :corrosion,
                                :action_req, :action_desc, :ref
                            )
                        """), {
                            "asset_id": i_asset, "i_date": str(i_date), "i_type": i_type,
                            "inspector": inspector, "score": i_score, "condition": condition,
                            "findings": findings_count, "critical": critical_findings,
                            "corrosion": corrosion_rate,
                            "action_req": int(findings_count > 0 or critical_findings > 0),
                            "action_desc": i_notes if findings_count > 0 else None,
                            "ref": insp_ref,
                        })
                        conn.commit()
                    st.success(f"✅ Inspection saved! Ref: {insp_ref} | Score: {i_score}/100 — {condition}")
                except Exception as e:
                    st.error(f"Error saving record: {e}")

    # ── TAB 4: OPERATING DATA ─────────────────────────────────────────
    with tab4:
        section_header("Log Daily Operating Data")
        with st.form("operating_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                o_asset = st.selectbox("Asset *", options=list(ASSET_REGISTRY.keys()),
                    format_func=lambda x: f"{x} — {ASSET_REGISTRY[x]['name']}", key="o_asset")
                o_date = st.date_input("Record Date *", value=date.today(), key="o_date")
                is_running = st.checkbox("Asset Running?", value=True)
                operating_hrs = st.number_input("Operating Hours", min_value=0.0, max_value=24.0, value=24.0, step=0.5)
                downtime_hrs = st.number_input("Downtime Hours", min_value=0.0, max_value=24.0, value=0.0, step=0.5)
            with col2:
                vibration = st.number_input("Vibration (mm/s)", min_value=0.0, max_value=20.0, value=1.8, step=0.01,
                    help="ISO 10816: <2.3 Normal | 2.3-4.5 Satisfactory | 4.5-7.1 Alarm | >7.1 Shutdown")
                temperature = st.number_input("Temperature (°C)", min_value=0.0, max_value=300.0, value=70.0, step=0.5)
                pressure = st.number_input("Pressure (bar)", min_value=0.0, max_value=200.0, value=40.0, step=0.5)
                efficiency = st.number_input("Efficiency (%)", min_value=0.0, max_value=100.0, value=88.0, step=0.1)
                power_kw = st.number_input("Power (kW)", min_value=0.0, max_value=5000.0, value=185.0, step=1.0)

            vib_color = THEME["red"] if vibration >= 7.1 else THEME["amber"] if vibration >= 4.5 else THEME["blue"] if vibration >= 2.3 else THEME["green"]
            vib_label = "Zone D — SHUTDOWN" if vibration >= 7.1 else "Zone C — ALARM" if vibration >= 4.5 else "Zone B — Satisfactory" if vibration >= 2.3 else "Zone A — Normal"
            st.markdown(f'<div style="color:{vib_color};font-weight:700;font-size:13px;">ISO 10816: {vib_label}</div>', unsafe_allow_html=True)

            if st.form_submit_button("💾 Save Operating Data", use_container_width=True, type="primary"):
                try:
                    engine = get_engine()
                    with engine.connect() as conn:
                        last = conn.execute(text("""
                            SELECT operating_hours_cumulative, runtime_hours_ytd, downtime_hours_ytd
                            FROM asset_operating_data WHERE asset_id = :id ORDER BY record_date DESC LIMIT 1
                        """), {"id": o_asset}).fetchone()
                        cum_hrs = (last[0] if last else 0) + operating_hrs
                        ytd_run = (last[1] if last else 0) + operating_hrs
                        ytd_dt  = (last[2] if last else 0) + downtime_hrs
                        exists = conn.execute(text(
                            "SELECT COUNT(*) FROM asset_operating_data WHERE asset_id=:id AND record_date=:date"
                        ), {"id": o_asset, "date": str(o_date)}).scalar()
                        if exists > 0:
                            conn.execute(text("""
                                UPDATE asset_operating_data SET
                                    operating_hours_daily=:op, downtime_hours_daily=:dt,
                                    vibration_mm_s=:vib, operating_temp_c=:temp,
                                    operating_pressure_bar=:pres, efficiency_pct=:eff,
                                    power_consumption_kw=:power, is_running=:running
                                WHERE asset_id=:id AND record_date=:date
                            """), {"op": operating_hrs, "dt": downtime_hrs, "vib": vibration,
                                   "temp": temperature, "pres": pressure, "eff": efficiency,
                                   "power": power_kw, "running": int(is_running),
                                   "id": o_asset, "date": str(o_date)})
                        else:
                            conn.execute(text("""
                                INSERT INTO asset_operating_data (
                                    asset_id, record_date, operating_hours_daily,
                                    operating_hours_cumulative, runtime_hours_ytd,
                                    downtime_hours_daily, downtime_hours_ytd,
                                    operating_temp_c, operating_pressure_bar,
                                    vibration_mm_s, power_consumption_kw,
                                    efficiency_pct, is_running
                                ) VALUES (
                                    :id, :date, :op, :cum, :ytd_run,
                                    :dt, :ytd_dt, :temp, :pres, :vib, :power, :eff, :running
                                )
                            """), {"id": o_asset, "date": str(o_date), "op": operating_hrs,
                                   "cum": cum_hrs, "ytd_run": ytd_run, "dt": downtime_hrs,
                                   "ytd_dt": ytd_dt, "temp": temperature, "pres": pressure,
                                   "vib": vibration, "power": power_kw, "eff": efficiency,
                                   "running": int(is_running)})
                        conn.commit()
                    st.success(f"✅ Operating data saved for {o_asset} on {o_date}")
                except Exception as e:
                    st.error(f"Error saving record: {e}")

    # ── RECENT ENTRIES ────────────────────────────────────────────────
    st.markdown("<br>", unsafe_allow_html=True)
    section_header("Recent Entries")
    engine = get_engine()
    col_r1, col_r2 = st.columns(2)
    with col_r1:
        st.markdown("**Recent Failure Events**")
        try:
            df = pd.read_sql("""
                SELECT failure_date, asset_id, failure_category, failure_severity, downtime_hours
                FROM failure_events ORDER BY rowid DESC LIMIT 5
            """, engine)
            st.dataframe(df, use_container_width=True, hide_index=True) if not df.empty else st.caption("None yet.")
        except Exception:
            pass
    with col_r2:
        st.markdown("**Recent Maintenance Records**")
        try:
            df = pd.read_sql("""
                SELECT maintenance_date, asset_id, maintenance_type, actual_cost_usd
                FROM maintenance_records ORDER BY rowid DESC LIMIT 5
            """, engine)
            st.dataframe(df, use_container_width=True, hide_index=True) if not df.empty else st.caption("None yet.")
        except Exception:
            pass
