"""
ORPMI Dashboard Data Layer
===========================
All SQL queries and DataFrame transformations consumed by the dashboard.
Centralises data access, enables caching, and keeps page code clean.
"""

import sys
from pathlib import Path
from functools import lru_cache

import pandas as pd
import numpy as np
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from database.db_connection import get_engine
from config.settings import ASSET_REGISTRY, KPI_THRESHOLDS


# ─────────────────────────────────────────────
# ENGINE
# ─────────────────────────────────────────────
_engine = None

def engine():
    global _engine
    if _engine is None:
        _engine = get_engine()
    return _engine


def sql(query: str, params: dict = None) -> pd.DataFrame:
    """Execute SQL and return DataFrame. Centralised for error handling."""
    try:
        return pd.read_sql(query, engine(), params=params)
    except Exception as e:
        return pd.DataFrame()


# ─────────────────────────────────────────────
# ASSETS
# ─────────────────────────────────────────────
def get_assets() -> pd.DataFrame:
    return sql("SELECT * FROM assets WHERE is_active=1 ORDER BY criticality_score DESC")


def get_asset_ids() -> list:
    df = get_assets()
    return df["asset_id"].tolist() if not df.empty else []


# ─────────────────────────────────────────────
# KPI SNAPSHOTS
# ─────────────────────────────────────────────
def get_latest_kpis() -> pd.DataFrame:
    return sql("""
        SELECT k.*, a.asset_name, a.asset_type, a.criticality,
               a.criticality_score, a.downtime_cost_usd_per_hr,
               a.target_availability_pct, a.replacement_cost_usd
        FROM kpi_daily_summary k
        JOIN assets a ON k.asset_id = a.asset_id
        WHERE k.summary_date = (SELECT MAX(summary_date) FROM kpi_daily_summary)
        ORDER BY k.maintenance_priority_score DESC
    """)


def get_kpi_timeseries(asset_ids: list = None, start_date: str = None, end_date: str = None) -> pd.DataFrame:
    where_clauses = ["1=1"]
    if asset_ids:
        ids = "','".join(asset_ids)
        where_clauses.append(f"k.asset_id IN ('{ids}')")
    if start_date:
        where_clauses.append(f"k.summary_date >= '{start_date}'")
    if end_date:
        where_clauses.append(f"k.summary_date <= '{end_date}'")
    where = " AND ".join(where_clauses)
    return sql(f"""
        SELECT k.asset_id, a.asset_name, a.criticality, k.summary_date,
               k.availability_pct, k.reliability_score, k.health_score,
               k.mtbf_hrs, k.mttr_hrs, k.downtime_hrs, k.failure_count,
               k.maintenance_compliance_pct, k.maintenance_cost_usd,
               k.risk_level, k.failure_probability_30d, k.maintenance_priority_score
        FROM kpi_daily_summary k
        JOIN assets a ON k.asset_id = a.asset_id
        WHERE {where}
        ORDER BY k.summary_date, k.asset_id
    """)


def get_monthly_kpis(asset_ids: list = None) -> pd.DataFrame:
    where = ""
    if asset_ids:
        ids = "','".join(asset_ids)
        where = f"WHERE asset_id IN ('{ids}')"
    return sql(f"""
        SELECT asset_id,
               strftime('%Y-%m', summary_date) AS year_month,
               AVG(availability_pct)           AS avg_availability,
               AVG(reliability_score)          AS avg_reliability,
               AVG(health_score)               AS avg_health_score,
               AVG(mtbf_hrs)                   AS avg_mtbf,
               AVG(mttr_hrs)                   AS avg_mttr,
               SUM(downtime_hrs)               AS total_downtime_hrs,
               SUM(failure_count)              AS total_failures,
               AVG(maintenance_compliance_pct) AS avg_compliance,
               SUM(maintenance_cost_usd)       AS total_maint_cost
        FROM kpi_daily_summary
        {where}
        GROUP BY asset_id, strftime('%Y-%m', summary_date)
        ORDER BY year_month, asset_id
    """)


# ─────────────────────────────────────────────
# FAILURES
# ─────────────────────────────────────────────
def get_failure_events(asset_ids: list = None) -> pd.DataFrame:
    where = ""
    if asset_ids:
        ids = "','".join(asset_ids)
        where = f"AND f.asset_id IN ('{ids}')"
    return sql(f"""
        SELECT f.*, a.asset_name, a.asset_type, a.criticality
        FROM failure_events f
        JOIN assets a ON f.asset_id = a.asset_id
        WHERE 1=1 {where}
        ORDER BY f.failure_date DESC
    """)


def get_failure_pareto() -> pd.DataFrame:
    return sql("""
        SELECT failure_category,
               COUNT(*) AS failure_count,
               SUM(downtime_hours) AS total_downtime_hrs,
               SUM(financial_impact_usd) AS total_impact_usd,
               ROUND(AVG(time_to_repair_hrs),1) AS avg_ttr_hrs,
               ROUND(COUNT(*)*100.0/SUM(COUNT(*)) OVER(),1) AS pct_of_total
        FROM failure_events
        GROUP BY failure_category
        ORDER BY failure_count DESC
    """)


def get_failures_by_month() -> pd.DataFrame:
    return sql("""
        SELECT strftime('%Y-%m', failure_date) AS month,
               asset_id,
               COUNT(*) AS failures,
               SUM(downtime_hours) AS total_downtime,
               SUM(financial_impact_usd) AS total_impact
        FROM failure_events
        GROUP BY month, asset_id
        ORDER BY month
    """)


def get_failures_by_asset() -> pd.DataFrame:
    return sql("""
        SELECT f.asset_id, a.asset_name, a.criticality,
               COUNT(*) AS total_failures,
               SUM(f.downtime_hours) AS total_downtime_hrs,
               SUM(f.financial_impact_usd) AS total_impact_usd,
               AVG(f.time_to_repair_hrs) AS avg_ttr_hrs,
               SUM(CASE WHEN f.failure_severity='Critical' THEN 1 ELSE 0 END) AS critical_failures
        FROM failure_events f
        JOIN assets a ON f.asset_id = a.asset_id
        GROUP BY f.asset_id, a.asset_name, a.criticality
        ORDER BY total_failures DESC
    """)


# ─────────────────────────────────────────────
# MAINTENANCE
# ─────────────────────────────────────────────
def get_maintenance_records(asset_ids: list = None) -> pd.DataFrame:
    where = ""
    if asset_ids:
        ids = "','".join(asset_ids)
        where = f"AND m.asset_id IN ('{ids}')"
    return sql(f"""
        SELECT m.*, a.asset_name, a.criticality
        FROM maintenance_records m
        JOIN assets a ON m.asset_id = a.asset_id
        WHERE 1=1 {where}
        ORDER BY m.maintenance_date DESC
    """)


def get_maintenance_cost_by_type() -> pd.DataFrame:
    return sql("""
        SELECT maintenance_type,
               COUNT(*) AS work_orders,
               SUM(actual_cost_usd) AS total_cost,
               AVG(actual_cost_usd) AS avg_cost,
               AVG(duration_hrs) AS avg_duration_hrs,
               SUM(CASE WHEN compliance_flag=1 THEN 1 ELSE 0 END)*100.0/COUNT(*) AS compliance_pct
        FROM maintenance_records
        GROUP BY maintenance_type
        ORDER BY total_cost DESC
    """)


def get_maintenance_compliance_by_asset() -> pd.DataFrame:
    return sql("""
        SELECT m.asset_id, a.asset_name, a.criticality,
               COUNT(*) AS total_wo,
               SUM(m.compliance_flag) AS compliant_wo,
               ROUND(SUM(m.compliance_flag)*100.0/COUNT(*),1) AS compliance_pct,
               SUM(m.actual_cost_usd) AS total_cost,
               AVG(m.overdue_days) AS avg_overdue_days
        FROM maintenance_records m
        JOIN assets a ON m.asset_id = a.asset_id
        GROUP BY m.asset_id, a.asset_name, a.criticality
        ORDER BY compliance_pct ASC
    """)


# ─────────────────────────────────────────────
# OPERATING DATA
# ─────────────────────────────────────────────
def get_operating_data(asset_id: str, start_date: str = None, end_date: str = None) -> pd.DataFrame:
    where_extra = ""
    if start_date:
        where_extra += f" AND record_date >= '{start_date}'"
    if end_date:
        where_extra += f" AND record_date <= '{end_date}'"
    return sql(f"""
        SELECT * FROM asset_operating_data
        WHERE asset_id = '{asset_id}' {where_extra}
        ORDER BY record_date
    """)


def get_downtime_log() -> pd.DataFrame:
    return sql("""
        SELECT d.*, a.asset_name, a.criticality
        FROM downtime_log d
        JOIN assets a ON d.asset_id = a.asset_id
        ORDER BY d.downtime_start DESC
    """)


# ─────────────────────────────────────────────
# INSPECTION
# ─────────────────────────────────────────────
def get_inspection_records(asset_ids: list = None) -> pd.DataFrame:
    where = ""
    if asset_ids:
        ids = "','".join(asset_ids)
        where = f"AND i.asset_id IN ('{ids}')"
    return sql(f"""
        SELECT i.*, a.asset_name
        FROM inspection_records i
        JOIN assets a ON i.asset_id = a.asset_id
        WHERE 1=1 {where}
        ORDER BY i.inspection_date DESC
    """)


# ─────────────────────────────────────────────
# EXECUTIVE SUMMARY AGGREGATIONS
# ─────────────────────────────────────────────
def get_facility_summary() -> dict:
    """Single-call aggregation for the executive overview page."""
    kpis = get_latest_kpis()
    failures = get_failure_events()
    maintenance = get_maintenance_records()

    if kpis.empty:
        return {}

    total_downtime_cost = (
        failures["downtime_hours"].fillna(0) * failures["asset_id"].map(
            {k: v["downtime_cost_usd_per_hr"] for k, v in ASSET_REGISTRY.items()}
        )
    ).sum() if not failures.empty else 0

    return {
        "fleet_availability": round(kpis["availability_pct"].mean(), 1),
        "fleet_health_score": round(kpis["health_score"].mean(), 1),
        "fleet_reliability": round(kpis["reliability_score"].mean(), 1),
        "avg_mtbf": round(kpis["mtbf_hrs"].mean(), 0),
        "avg_mttr": round(kpis["mttr_hrs"].mean(), 1),
        "total_failures_ytd": len(failures),
        "total_downtime_hrs_ytd": round(failures["downtime_hours"].sum(), 1) if not failures.empty else 0,
        "total_downtime_cost_usd": round(total_downtime_cost, 0),
        "total_maintenance_cost_usd": round(maintenance["actual_cost_usd"].sum(), 0) if not maintenance.empty else 0,
        "critical_assets": len(kpis[kpis["risk_level"].isin(["Critical", "High"])]),
        "assets_below_target_availability": len(kpis[kpis["availability_pct"] < kpis["target_availability_pct"]]),
        "maintenance_compliance": round(kpis["maintenance_compliance_pct"].mean(), 1),
        "total_assets": len(kpis),
        "high_risk_assets": kpis[kpis["risk_level"].isin(["Critical", "High"])]["asset_id"].tolist(),
    }


def get_rag_color(value: float, green_threshold: float, amber_threshold: float, higher_is_better: bool = True) -> str:
    if higher_is_better:
        if value >= green_threshold:
            return "green"
        elif value >= amber_threshold:
            return "amber"
        return "red"
    else:
        if value <= green_threshold:
            return "green"
        elif value <= amber_threshold:
            return "amber"
        return "red"
