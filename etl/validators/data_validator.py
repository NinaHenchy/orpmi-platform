"""
ORPMI Data Validation Framework
================================
Validates every dataset before it enters the database.
Enforces business rules, referential integrity, and sensor physics.
Produces a structured validation report per ETL run.
"""

import sys
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Optional

import pandas as pd
import numpy as np
from loguru import logger

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from config.settings import ASSET_REGISTRY, KPI_THRESHOLDS


@dataclass
class ValidationResult:
    table: str
    check_name: str
    status: str          # PASS / WARN / FAIL
    records_checked: int
    records_failed: int
    message: str
    severity: str = "INFO"   # INFO / WARNING / ERROR / CRITICAL

    @property
    def passed(self) -> bool:
        return self.status == "PASS"


@dataclass
class ValidationReport:
    run_timestamp: str
    results: List[ValidationResult] = field(default_factory=list)

    def add(self, result: ValidationResult):
        self.results.append(result)

    @property
    def passed(self) -> bool:
        return all(r.status != "FAIL" for r in self.results)

    @property
    def critical_failures(self) -> List[ValidationResult]:
        return [r for r in self.results if r.status == "FAIL"]

    @property
    def warnings(self) -> List[ValidationResult]:
        return [r for r in self.results if r.status == "WARN"]

    def summary(self) -> str:
        total = len(self.results)
        passed = sum(1 for r in self.results if r.status == "PASS")
        warned = sum(1 for r in self.results if r.status == "WARN")
        failed = sum(1 for r in self.results if r.status == "FAIL")
        return (f"Validation Summary: {total} checks | "
                f"{passed} PASS | {warned} WARN | {failed} FAIL")

    def to_dataframe(self) -> pd.DataFrame:
        return pd.DataFrame([{
            "table": r.table,
            "check_name": r.check_name,
            "status": r.status,
            "records_checked": r.records_checked,
            "records_failed": r.records_failed,
            "message": r.message,
            "severity": r.severity,
        } for r in self.results])


VALID_ASSET_IDS = set(ASSET_REGISTRY.keys())
VALID_CRITICALITIES = {"Critical", "High", "Medium", "Low"}
VALID_FAILURE_SEVERITIES = {"Critical", "Major", "Minor", "Negligible"}
VALID_CONDITIONS = {"Excellent", "Good", "Fair", "Poor", "Critical"}
VALID_RISK_LEVELS = {"Low", "Medium", "High", "Critical"}


def validate_assets(df: pd.DataFrame) -> List[ValidationResult]:
    results = []
    table = "assets"

    # Completeness — primary key
    nulls = df["asset_id"].isnull().sum()
    results.append(ValidationResult(
        table, "primary_key_not_null", "PASS" if nulls == 0 else "FAIL",
        len(df), nulls, f"asset_id null count: {nulls}", "ERROR"
    ))

    # Uniqueness — no duplicate asset IDs
    dupes = df["asset_id"].duplicated().sum()
    results.append(ValidationResult(
        table, "primary_key_unique", "PASS" if dupes == 0 else "FAIL",
        len(df), dupes, f"Duplicate asset_id count: {dupes}", "ERROR"
    ))

    # Criticality domain check
    invalid_crit = (~df["criticality"].isin(VALID_CRITICALITIES)).sum()
    results.append(ValidationResult(
        table, "criticality_domain", "PASS" if invalid_crit == 0 else "FAIL",
        len(df), invalid_crit,
        f"Invalid criticality values: {invalid_crit}", "ERROR"
    ))

    # Replacement cost > 0
    neg_cost = (df["replacement_cost_usd"] <= 0).sum()
    results.append(ValidationResult(
        table, "replacement_cost_positive", "PASS" if neg_cost == 0 else "WARN",
        len(df), neg_cost, f"Non-positive replacement costs: {neg_cost}", "WARNING"
    ))

    # Commission year plausible
    invalid_year = ((df["commission_year"] < 1980) | (df["commission_year"] > 2025)).sum()
    results.append(ValidationResult(
        table, "commission_year_range", "PASS" if invalid_year == 0 else "WARN",
        len(df), invalid_year, f"Implausible commission years: {invalid_year}", "WARNING"
    ))

    return results


def validate_operating_data(df: pd.DataFrame) -> List[ValidationResult]:
    results = []
    table = "asset_operating_data"

    # Asset ID referential integrity
    invalid_assets = (~df["asset_id"].isin(VALID_ASSET_IDS)).sum()
    results.append(ValidationResult(
        table, "asset_id_referential_integrity", "PASS" if invalid_assets == 0 else "FAIL",
        len(df), invalid_assets, f"Unknown asset_ids: {invalid_assets}", "CRITICAL"
    ))

    # Daily operating hours must be 0–24
    invalid_ops_hrs = ((df["operating_hours_daily"] < 0) | (df["operating_hours_daily"] > 24)).sum()
    results.append(ValidationResult(
        table, "operating_hours_range", "PASS" if invalid_ops_hrs == 0 else "FAIL",
        len(df), invalid_ops_hrs, f"Operating hours out of 0-24 range: {invalid_ops_hrs}", "ERROR"
    ))

    # Downtime + operating must not exceed 24h
    total_hrs = df["operating_hours_daily"] + df["downtime_hours_daily"]
    exceeds_24 = (total_hrs > 24.1).sum()
    results.append(ValidationResult(
        table, "total_hours_max_24", "PASS" if exceeds_24 == 0 else "FAIL",
        len(df), exceeds_24, f"Records where ops+downtime > 24h: {exceeds_24}", "ERROR"
    ))

    # Vibration — ISO 10816 upper physical limit check
    vib_data = df["vibration_mm_s"].dropna()
    vib_extreme = (vib_data > 20.0).sum()
    results.append(ValidationResult(
        table, "vibration_physical_limit", "PASS" if vib_extreme == 0 else "WARN",
        len(vib_data), vib_extreme, f"Vibration readings > 20 mm/s: {vib_extreme}", "WARNING"
    ))

    # Temperature — no physically impossible negative values
    temp_data = df["operating_temp_c"].dropna()
    neg_temps = (temp_data < 0).sum()
    results.append(ValidationResult(
        table, "temperature_non_negative", "PASS" if neg_temps == 0 else "WARN",
        len(temp_data), neg_temps, f"Negative temperature readings: {neg_temps}", "WARNING"
    ))

    # Efficiency — must be 0–100%
    eff_data = df["efficiency_pct"].dropna()
    invalid_eff = ((eff_data < 0) | (eff_data > 100)).sum()
    results.append(ValidationResult(
        table, "efficiency_percentage_range", "PASS" if invalid_eff == 0 else "FAIL",
        len(eff_data), invalid_eff, f"Efficiency values outside 0-100%: {invalid_eff}", "ERROR"
    ))

    # Duplicate (asset_id, record_date) check
    dupes = df.duplicated(subset=["asset_id", "record_date"]).sum()
    results.append(ValidationResult(
        table, "unique_asset_date_combination", "PASS" if dupes == 0 else "FAIL",
        len(df), dupes, f"Duplicate (asset, date) combinations: {dupes}", "ERROR"
    ))

    # Completeness — null check on key fields
    null_vibration = df["vibration_mm_s"].isnull().sum()
    null_pct = null_vibration / len(df) * 100
    status = "PASS" if null_pct < 5 else "WARN" if null_pct < 15 else "FAIL"
    results.append(ValidationResult(
        table, "vibration_completeness", status,
        len(df), null_vibration,
        f"Null vibration readings: {null_vibration} ({null_pct:.1f}%)", "WARNING"
    ))

    return results


def validate_failure_events(df: pd.DataFrame) -> List[ValidationResult]:
    results = []
    table = "failure_events"

    if df.empty:
        results.append(ValidationResult(
            table, "non_empty_check", "WARN", 0, 0,
            "Failure events dataset is empty — check generation.", "WARNING"
        ))
        return results

    # Asset ID integrity
    invalid_assets = (~df["asset_id"].isin(VALID_ASSET_IDS)).sum()
    results.append(ValidationResult(
        table, "asset_id_referential_integrity", "PASS" if invalid_assets == 0 else "FAIL",
        len(df), invalid_assets, f"Unknown asset_ids: {invalid_assets}", "CRITICAL"
    ))

    # Severity domain
    invalid_sev = (~df["failure_severity"].isin(VALID_FAILURE_SEVERITIES)).sum()
    results.append(ValidationResult(
        table, "failure_severity_domain", "PASS" if invalid_sev == 0 else "FAIL",
        len(df), invalid_sev, f"Invalid severity values: {invalid_sev}", "ERROR"
    ))

    # Downtime hours > 0
    zero_downtime = (df["downtime_hours"] <= 0).sum()
    results.append(ValidationResult(
        table, "downtime_hours_positive", "PASS" if zero_downtime == 0 else "WARN",
        len(df), zero_downtime, f"Failure events with zero downtime: {zero_downtime}", "WARNING"
    ))

    # Downtime hours < 8760 (one year max)
    extreme_downtime = (df["downtime_hours"] > 8760).sum()
    results.append(ValidationResult(
        table, "downtime_hours_max", "PASS" if extreme_downtime == 0 else "FAIL",
        len(df), extreme_downtime, f"Downtime hours exceeding 1 year: {extreme_downtime}", "ERROR"
    ))

    # Financial impact — no negatives
    if "financial_impact_usd" in df.columns:
        neg_impact = (df["financial_impact_usd"] < 0).sum()
        results.append(ValidationResult(
            table, "financial_impact_non_negative", "PASS" if neg_impact == 0 else "WARN",
            len(df), neg_impact, f"Negative financial impacts: {neg_impact}", "WARNING"
        ))

    return results


def validate_maintenance_records(df: pd.DataFrame) -> List[ValidationResult]:
    results = []
    table = "maintenance_records"

    # Work order ID uniqueness
    dupes = df["work_order_id"].duplicated().sum()
    results.append(ValidationResult(
        table, "work_order_id_unique", "PASS" if dupes == 0 else "FAIL",
        len(df), dupes, f"Duplicate work order IDs: {dupes}", "ERROR"
    ))

    # Asset ID integrity
    invalid_assets = (~df["asset_id"].isin(VALID_ASSET_IDS)).sum()
    results.append(ValidationResult(
        table, "asset_id_referential_integrity", "PASS" if invalid_assets == 0 else "FAIL",
        len(df), invalid_assets, f"Unknown asset_ids: {invalid_assets}", "CRITICAL"
    ))

    # Compliance flag domain (0 or 1 only)
    invalid_flag = (~df["compliance_flag"].isin([0, 1])).sum()
    results.append(ValidationResult(
        table, "compliance_flag_domain", "PASS" if invalid_flag == 0 else "FAIL",
        len(df), invalid_flag, f"Invalid compliance flag values: {invalid_flag}", "ERROR"
    ))

    # Actual cost > 0
    neg_cost = (df["actual_cost_usd"] < 0).sum()
    results.append(ValidationResult(
        table, "actual_cost_non_negative", "PASS" if neg_cost == 0 else "WARN",
        len(df), neg_cost, f"Negative actual maintenance costs: {neg_cost}", "WARNING"
    ))

    return results


def validate_kpi_summary(df: pd.DataFrame) -> List[ValidationResult]:
    results = []
    table = "kpi_daily_summary"

    # Availability 0–100
    avail_data = df["availability_pct"].dropna()
    invalid_avail = ((avail_data < 0) | (avail_data > 100)).sum()
    results.append(ValidationResult(
        table, "availability_range", "PASS" if invalid_avail == 0 else "FAIL",
        len(avail_data), invalid_avail, f"Availability outside 0-100%: {invalid_avail}", "ERROR"
    ))

    # Health score 0–100
    health_data = df["health_score"].dropna()
    invalid_health = ((health_data < 0) | (health_data > 100)).sum()
    results.append(ValidationResult(
        table, "health_score_range", "PASS" if invalid_health == 0 else "FAIL",
        len(health_data), invalid_health, f"Health scores outside 0-100: {invalid_health}", "ERROR"
    ))

    # Failure probability 0–1
    prob_data = df["failure_probability_30d"].dropna()
    invalid_prob = ((prob_data < 0) | (prob_data > 1)).sum()
    results.append(ValidationResult(
        table, "failure_probability_range", "PASS" if invalid_prob == 0 else "FAIL",
        len(prob_data), invalid_prob, f"Failure probabilities outside 0-1: {invalid_prob}", "ERROR"
    ))

    # Risk level domain
    invalid_risk = (~df["risk_level"].isin(VALID_RISK_LEVELS)).sum()
    results.append(ValidationResult(
        table, "risk_level_domain", "PASS" if invalid_risk == 0 else "FAIL",
        len(df), invalid_risk, f"Invalid risk levels: {invalid_risk}", "ERROR"
    ))

    # Coverage — all assets should have KPIs
    assets_in_kpi = set(df["asset_id"].unique())
    missing_assets = VALID_ASSET_IDS - assets_in_kpi
    results.append(ValidationResult(
        table, "all_assets_covered", "PASS" if not missing_assets else "FAIL",
        len(VALID_ASSET_IDS), len(missing_assets),
        f"Assets missing KPI records: {missing_assets}", "CRITICAL"
    ))

    return results


def validate_inspection_records(df: pd.DataFrame) -> List[ValidationResult]:
    results = []
    table = "inspection_records"

    # Inspection score 0–100
    score_data = df["inspection_score"].dropna()
    invalid_score = ((score_data < 0) | (score_data > 100)).sum()
    results.append(ValidationResult(
        table, "inspection_score_range", "PASS" if invalid_score == 0 else "FAIL",
        len(score_data), invalid_score, f"Inspection scores outside 0-100: {invalid_score}", "ERROR"
    ))

    # Overall condition domain
    invalid_cond = (~df["overall_condition"].isin(VALID_CONDITIONS)).sum()
    results.append(ValidationResult(
        table, "condition_domain", "PASS" if invalid_cond == 0 else "FAIL",
        len(df), invalid_cond, f"Invalid condition values: {invalid_cond}", "ERROR"
    ))

    return results


def run_full_validation(datasets: dict) -> ValidationReport:
    """
    Run all validation checks across all datasets.
    Returns a structured report. ETL pipeline aborts on CRITICAL failures.
    """
    from datetime import datetime
    report = ValidationReport(run_timestamp=datetime.now().isoformat())

    validators = {
        "assets": validate_assets,
        "asset_operating_data": validate_operating_data,
        "failure_events": validate_failure_events,
        "maintenance_records": validate_maintenance_records,
        "kpi_daily_summary": validate_kpi_summary,
        "inspection_records": validate_inspection_records,
    }

    for table_name, validator_fn in validators.items():
        if table_name in datasets and not datasets[table_name].empty:
            check_results = validator_fn(datasets[table_name])
            for r in check_results:
                report.add(r)
                log_fn = logger.success if r.passed else (logger.warning if r.status == "WARN" else logger.error)
                log_fn(f"  [{r.status}] {r.table}.{r.check_name}: {r.message}")

    logger.info(report.summary())
    return report


if __name__ == "__main__":
    from etl.extractors.synthetic_data_generator import run_full_generation
    data = run_full_generation()
    report = run_full_validation(data)
    print(report.to_dataframe().to_string())
