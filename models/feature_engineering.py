"""
ORPMI Feature Engineering Pipeline
=====================================
Constructs the ML feature matrix from raw operational data.

Design philosophy:
  Every feature has an operational justification — no feature is included
  purely because it improves model metrics. Each feature maps to a physical
  mechanism that a reliability engineer would recognise.

Feature groups:
  1. Sensor statistics      — rolling mean/std/max of vibration, temp, pressure
  2. Degradation signals    — efficiency trend, vibration trend slopes
  3. Operating stress       — hours since last maintenance, cumulative hours
  4. Historical failure     — failure frequency, recency, severity weighting
  5. Inspection condition   — latest inspection score, condition trend
  6. KPI-derived features   — MTBF deviation, availability trend, compliance

Target variable:
  binary_failure_30d  — 1 if a failure occurs within the next 30 days, 0 otherwise
  This is a classification problem (failure / no failure).
  The output is then calibrated to produce a probability score.
"""

import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from loguru import logger

warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from database.db_connection import get_engine
from config.settings import ASSET_REGISTRY

FEATURE_WINDOWS = [7, 14, 30]   # Rolling window sizes (days)
FORECAST_HORIZON = 30            # Days ahead we are predicting failure


def load_raw_data() -> dict:
    engine = get_engine()
    tables = {
        "ops":        "SELECT * FROM asset_operating_data ORDER BY asset_id, record_date",
        "kpi":        "SELECT * FROM kpi_daily_summary ORDER BY asset_id, summary_date",
        "failures":   "SELECT * FROM failure_events ORDER BY asset_id, failure_date",
        "maintenance":"SELECT * FROM maintenance_records ORDER BY asset_id, maintenance_date",
        "inspection": "SELECT * FROM inspection_records ORDER BY asset_id, inspection_date",
    }
    data = {}
    for name, query in tables.items():
        data[name] = pd.read_sql(query, engine)
    logger.info(f"Raw data loaded: {', '.join(f'{k}={len(v)}' for k, v in data.items())}")
    return data


def build_failure_labels(ops: pd.DataFrame, failures: pd.DataFrame) -> pd.DataFrame:
    """
    For each (asset_id, date) record, set label=1 if a failure occurs
    within the next FORECAST_HORIZON days.

    This converts the regression-style continuous failure probability
    in kpi_daily_summary into a true binary classification target,
    enabling proper model training and calibration.
    """
    ops = ops.copy()
    ops["record_date"] = pd.to_datetime(ops["record_date"])
    failures = failures.copy()
    failures["failure_date"] = pd.to_datetime(failures["failure_date"])

    labels = []
    for _, row in ops.iterrows():
        asset_id = row["asset_id"]
        date = row["record_date"]
        horizon_end = date + pd.Timedelta(days=FORECAST_HORIZON)

        # Any failure on this asset within the next 30 days?
        future_failures = failures[
            (failures["asset_id"] == asset_id) &
            (failures["failure_date"] > date) &
            (failures["failure_date"] <= horizon_end)
        ]
        has_failure = int(len(future_failures) > 0)

        # Severity-weighted label (not used for binary classification
        # but available for regression variant)
        severity_map = {"Critical": 4, "Major": 3, "Minor": 2, "Negligible": 1}
        if not future_failures.empty:
            max_severity_score = future_failures["failure_severity"].map(severity_map).max()
        else:
            max_severity_score = 0

        labels.append({
            "asset_id": asset_id,
            "record_date": date,
            "binary_failure_30d": has_failure,
            "max_severity_30d": max_severity_score,
            "days_to_next_failure": _days_to_next_failure(asset_id, date, failures),
        })

    return pd.DataFrame(labels)


def _days_to_next_failure(asset_id: str, current_date, failures: pd.DataFrame) -> float:
    future = failures[
        (failures["asset_id"] == asset_id) &
        (failures["failure_date"] > current_date)
    ]
    if future.empty:
        return 999.0
    return (future["failure_date"].min() - current_date).days


def build_sensor_features(ops: pd.DataFrame) -> pd.DataFrame:
    """
    Rolling statistical features from sensor time series.

    Reliability engineering rationale:
      - Vibration MEAN: baseline operating level — rising trend = bearing wear
      - Vibration MAX: spike detection — ISO 10816 zone exceedances
      - Vibration STD: increasing variation = emerging imbalance/misalignment
      - Temp MEAN: process operating point drift
      - Temp MAX: overtemperature events precede seal and bearing failures
      - Efficiency MEAN: gradual degradation signature for all rotating equipment
      - Efficiency SLOPE: rate of degradation — faster slope = higher urgency
    """
    ops = ops.copy()
    ops["record_date"] = pd.to_datetime(ops["record_date"])
    ops = ops.sort_values(["asset_id", "record_date"])

    feature_frames = []

    for asset_id, group in ops.groupby("asset_id"):
        group = group.set_index("record_date").sort_index()
        feats = pd.DataFrame(index=group.index)
        feats["asset_id"] = asset_id

        for window in FEATURE_WINDOWS:
            w = f"{window}d"
            # Vibration features
            if "vibration_mm_s" in group.columns:
                vib = group["vibration_mm_s"].ffill()
                feats[f"vib_mean_{window}d"]  = vib.rolling(w, min_periods=1).mean()
                feats[f"vib_max_{window}d"]   = vib.rolling(w, min_periods=1).max()
                feats[f"vib_std_{window}d"]   = vib.rolling(w, min_periods=1).std().fillna(0)
                feats[f"vib_p95_{window}d"]   = vib.rolling(w, min_periods=1).quantile(0.95)

            # Temperature features
            if "operating_temp_c" in group.columns:
                temp = group["operating_temp_c"].ffill()
                feats[f"temp_mean_{window}d"] = temp.rolling(w, min_periods=1).mean()
                feats[f"temp_max_{window}d"]  = temp.rolling(w, min_periods=1).max()

            # Pressure features
            if "operating_pressure_bar" in group.columns:
                pres = group["operating_pressure_bar"].ffill()
                feats[f"pres_mean_{window}d"] = pres.rolling(w, min_periods=1).mean()
                feats[f"pres_std_{window}d"]  = pres.rolling(w, min_periods=1).std().fillna(0)

            # Efficiency features
            if "efficiency_pct" in group.columns:
                eff = group["efficiency_pct"].ffill()
                feats[f"eff_mean_{window}d"]  = eff.rolling(w, min_periods=1).mean()
                feats[f"eff_min_{window}d"]   = eff.rolling(w, min_periods=1).min()

            # Downtime accumulation
            if "downtime_hours_daily" in group.columns:
                dt = group["downtime_hours_daily"].fillna(0)
                feats[f"downtime_sum_{window}d"] = dt.rolling(w, min_periods=1).sum()

        # Point-in-time sensor values
        feats["vibration_current"]   = group["vibration_mm_s"].ffill()
        feats["temp_current"]        = group["operating_temp_c"].ffill()
        feats["pressure_current"]    = group["operating_pressure_bar"].ffill()
        feats["efficiency_current"]  = group["efficiency_pct"].ffill()
        feats["power_current"]       = group["power_consumption_kw"].ffill()
        feats["is_running"]          = group["is_running"].fillna(1)

        # ISO 10816 zone flags
        feats["vib_zone_c_flag"] = (feats["vibration_current"] >= 4.5).astype(int)
        feats["vib_zone_d_flag"] = (feats["vibration_current"] >= 7.1).astype(int)

        feature_frames.append(feats.reset_index())

    result = pd.concat(feature_frames, ignore_index=True)
    result = result.rename(columns={"record_date": "date"})
    logger.info(f"Sensor features built: {len(result)} rows, {len(result.columns)} cols")
    return result


def build_degradation_features(ops: pd.DataFrame) -> pd.DataFrame:
    """
    Trend-based features capturing rate of change in key parameters.

    These are the most powerful predictive features — not the absolute value
    of vibration, but HOW FAST it is increasing. A compressor running at
    3.5 mm/s with a slope of +0.05 mm/s/day is more concerning than one
    at 4.0 mm/s that has been stable for 30 days.
    """
    ops = ops.copy()
    ops["record_date"] = pd.to_datetime(ops["record_date"])
    ops = ops.sort_values(["asset_id", "record_date"])

    degradation_rows = []

    for asset_id, group in ops.groupby("asset_id"):
        group = group.reset_index(drop=True)

        for i in range(len(group)):
            row_date = group.loc[i, "record_date"]
            row_feats = {"asset_id": asset_id, "date": row_date}

            # 14-day and 30-day slope calculations
            for window in [14, 30]:
                start_idx = max(0, i - window)
                subset = group.iloc[start_idx:i + 1]

                if len(subset) < 3:
                    row_feats[f"vib_slope_{window}d"]  = 0.0
                    row_feats[f"temp_slope_{window}d"] = 0.0
                    row_feats[f"eff_slope_{window}d"]  = 0.0
                    continue

                x = np.arange(len(subset))
                for col, feat_name in [
                    ("vibration_mm_s",   f"vib_slope_{window}d"),
                    ("operating_temp_c", f"temp_slope_{window}d"),
                    ("efficiency_pct",   f"eff_slope_{window}d"),
                ]:
                    vals = subset[col].ffill().fillna(0).values
                    if len(vals) > 1 and np.std(vals) > 0:
                        slope = np.polyfit(x, vals, 1)[0]
                    else:
                        slope = 0.0
                    row_feats[feat_name] = round(float(slope), 6)

            # Asset age factor (normalised 0–1)
            commission_year = ASSET_REGISTRY[asset_id]["commission_year"]
            age_years = (row_date.year - commission_year) + (row_date.dayofyear / 365)
            expected_life = 25.0  # typical rotating equipment design life
            row_feats["asset_age_normalised"] = min(age_years / expected_life, 1.0)

            # Days since commission (raw)
            row_feats["asset_age_days"] = int(
                (row_date - pd.Timestamp(f"{commission_year}-01-01")).days
            )

            # Cumulative operating hours at this point
            cum_hrs = group.loc[i, "operating_hours_cumulative"]
            overhaul_interval = ASSET_REGISTRY[asset_id]["overhaul_interval_hrs"]
            row_feats["overhaul_fraction"] = min(
                (cum_hrs % overhaul_interval) / overhaul_interval, 1.0
            )
            row_feats["cumulative_hours"] = cum_hrs

            degradation_rows.append(row_feats)

    result = pd.DataFrame(degradation_rows)
    logger.info(f"Degradation features built: {len(result)} rows")
    return result


def build_maintenance_features(ops: pd.DataFrame, maintenance: pd.DataFrame) -> pd.DataFrame:
    """
    Maintenance history features.

    Reliability rationale:
      - days_since_last_pm: PM overdue status drives failure probability
      - pm_compliance_30d: recent PM adherence indicates maintenance quality
      - days_to_next_pm: proximity to scheduled maintenance — assets approaching
        PM due dates show elevated wear if PM has been deferred
      - corrective_count_90d: frequency of corrective work = asset health signal
    """
    ops = ops.copy()
    ops["record_date"] = pd.to_datetime(ops["record_date"])
    maintenance = maintenance.copy()
    maintenance["maintenance_date"] = pd.to_datetime(maintenance["maintenance_date"])

    maint_rows = []

    for asset_id, ops_group in ops.groupby("asset_id"):
        asset_maint = maintenance[maintenance["asset_id"] == asset_id].sort_values("maintenance_date")
        pm_records = asset_maint[asset_maint["maintenance_type"] == "Preventive Maintenance"]
        cm_records = asset_maint[asset_maint["maintenance_type"].isin([
            "Corrective Maintenance", "Breakdown Maintenance"
        ])]
        pm_interval_days = ASSET_REGISTRY[asset_id]["pm_interval_days"]

        for _, row in ops_group.iterrows():
            date = pd.to_datetime(row["record_date"])
            feats = {"asset_id": asset_id, "date": date}

            # Days since last PM
            past_pm = pm_records[pm_records["maintenance_date"] <= date]
            if not past_pm.empty:
                last_pm = past_pm["maintenance_date"].max()
                feats["days_since_last_pm"] = (date - last_pm).days
                feats["pm_overdue_flag"]     = int((date - last_pm).days > pm_interval_days * 1.1)
            else:
                feats["days_since_last_pm"] = pm_interval_days * 2
                feats["pm_overdue_flag"]     = 1

            # PM compliance in last 90 days
            recent_pm = asset_maint[
                (asset_maint["maintenance_date"] >= date - pd.Timedelta(days=90)) &
                (asset_maint["maintenance_date"] <= date)
            ]
            if not recent_pm.empty:
                feats["pm_compliance_90d"]   = recent_pm["compliance_flag"].mean()
                feats["maintenance_cost_90d"] = recent_pm["actual_cost_usd"].sum()
            else:
                feats["pm_compliance_90d"]   = 0.5
                feats["maintenance_cost_90d"] = 0.0

            # Corrective maintenance frequency (last 90 days)
            recent_cm = cm_records[
                (cm_records["maintenance_date"] >= date - pd.Timedelta(days=90)) &
                (cm_records["maintenance_date"] <= date)
            ]
            feats["corrective_count_90d"] = len(recent_cm)

            # Days since last inspection
            maint_rows.append(feats)

    result = pd.DataFrame(maint_rows)
    logger.info(f"Maintenance features built: {len(result)} rows")
    return result


def build_failure_history_features(ops: pd.DataFrame, failures: pd.DataFrame) -> pd.DataFrame:
    """
    Historical failure pattern features.

    Reliability rationale:
      - failures_90d: recent failure frequency — the single strongest predictor
      - days_since_last_failure: recency effect — assets that recently failed
        have elevated re-failure probability (especially for recurring modes)
      - failure_severity_score_90d: weighted sum of recent failure severities —
        distinguishes between many minor events and one critical event
      - recurrence_rate: proportion of failures that are repeats — high
        recurrence indicates unresolved root cause
    """
    ops = ops.copy()
    ops["record_date"] = pd.to_datetime(ops["record_date"])
    failures = failures.copy()
    failures["failure_date"] = pd.to_datetime(failures["failure_date"])

    severity_weights = {"Critical": 4.0, "Major": 2.5, "Minor": 1.2, "Negligible": 0.5}
    hist_rows = []

    for asset_id, ops_group in ops.groupby("asset_id"):
        asset_failures = failures[failures["asset_id"] == asset_id].sort_values("failure_date")

        for _, row in ops_group.iterrows():
            date = pd.to_datetime(row["record_date"])
            feats = {"asset_id": asset_id, "date": date}

            past_failures = asset_failures[asset_failures["failure_date"] < date]

            # Failures in rolling windows
            for window in [30, 60, 90, 180]:
                window_start = date - pd.Timedelta(days=window)
                window_failures = past_failures[past_failures["failure_date"] >= window_start]
                feats[f"failures_{window}d"] = len(window_failures)
                feats[f"downtime_hrs_{window}d"] = window_failures["downtime_hours"].sum()
                feats[f"severity_score_{window}d"] = window_failures["failure_severity"].map(
                    severity_weights
                ).sum()

            # Days since last failure
            if not past_failures.empty:
                last_fail_date = past_failures["failure_date"].max()
                feats["days_since_last_failure"] = (date - last_fail_date).days
                feats["last_failure_severity"] = severity_weights.get(
                    past_failures.loc[past_failures["failure_date"].idxmax(), "failure_severity"], 0
                )
            else:
                feats["days_since_last_failure"] = 999
                feats["last_failure_severity"]   = 0.0

            # Recurrence rate (% of past failures that are marked recurrent)
            if not past_failures.empty and "is_recurrence" in past_failures.columns:
                feats["recurrence_rate"] = past_failures["is_recurrence"].mean()
            else:
                feats["recurrence_rate"] = 0.0

            # Total failures ever (life-of-asset)
            feats["total_failures_life"] = len(past_failures)

            hist_rows.append(feats)

    result = pd.DataFrame(hist_rows)
    logger.info(f"Failure history features built: {len(result)} rows")
    return result


def build_kpi_features(kpi: pd.DataFrame) -> pd.DataFrame:
    """
    KPI-derived features — captures operational trajectory.

    These tell the model not just current state but direction:
    is availability improving or declining? Is MTBF shrinking?
    """
    kpi = kpi.copy()
    kpi["summary_date"] = pd.to_datetime(kpi["summary_date"])
    kpi = kpi.sort_values(["asset_id", "summary_date"])

    kpi_feat_rows = []
    for asset_id, group in kpi.groupby("asset_id"):
        group = group.reset_index(drop=True)
        for i, row in group.iterrows():
            feats = {"asset_id": asset_id, "date": row["summary_date"]}

            feats["availability_current"]  = row["availability_pct"]
            feats["health_score_current"]  = row["health_score"]
            feats["reliability_current"]   = row["reliability_score"]
            feats["mtbf_current"]          = row["mtbf_hrs"]
            feats["compliance_current"]    = row["maintenance_compliance_pct"]

            # 30-day rolling trend in availability and health
            start_idx = max(0, i - 30)
            subset = group.iloc[start_idx:i + 1]
            if len(subset) >= 5:
                x = np.arange(len(subset))
                avail_slope = np.polyfit(x, subset["availability_pct"].values, 1)[0]
                health_slope = np.polyfit(x, subset["health_score"].values, 1)[0]
            else:
                avail_slope = 0.0
                health_slope = 0.0

            feats["availability_slope_30d"] = round(float(avail_slope), 6)
            feats["health_slope_30d"]       = round(float(health_slope), 6)

            # Asset criticality (static)
            feats["criticality_score"] = ASSET_REGISTRY[asset_id]["criticality_score"]

            kpi_feat_rows.append(feats)

    result = pd.DataFrame(kpi_feat_rows)
    logger.info(f"KPI features built: {len(result)} rows")
    return result


def build_full_feature_matrix() -> pd.DataFrame:
    """
    Master feature matrix constructor.
    Merges all feature groups on (asset_id, date) and attaches the binary label.
    """
    logger.info("=" * 60)
    logger.info("ORPMI Feature Engineering Pipeline — START")
    logger.info("=" * 60)

    raw = load_raw_data()

    logger.info("Building sensor features...")
    sensor_feats = build_sensor_features(raw["ops"])

    logger.info("Building degradation features...")
    degrad_feats = build_degradation_features(raw["ops"])

    logger.info("Building maintenance features...")
    maint_feats = build_maintenance_features(raw["ops"], raw["maintenance"])

    logger.info("Building failure history features...")
    hist_feats = build_failure_history_features(raw["ops"], raw["failures"])

    logger.info("Building KPI features...")
    kpi_feats = build_kpi_features(raw["kpi"])

    logger.info("Building labels...")
    labels = build_failure_labels(raw["ops"], raw["failures"])
    labels["date"] = pd.to_datetime(labels["record_date"])

    # Merge all feature groups
    logger.info("Merging feature groups...")
    base = sensor_feats.copy()
    base["date"] = pd.to_datetime(base["date"])

    for feat_df in [degrad_feats, maint_feats, hist_feats, kpi_feats]:
        feat_df["date"] = pd.to_datetime(feat_df["date"])
        # Drop asset_id before merge (already in base)
        merge_cols = [c for c in feat_df.columns if c not in ["asset_id"]]
        base = base.merge(
            feat_df[["asset_id", "date"] + [c for c in merge_cols if c != "date"]],
            on=["asset_id", "date"],
            how="left"
        )

    # Merge labels
    base = base.merge(
        labels[["asset_id", "date", "binary_failure_30d", "max_severity_30d",
                "days_to_next_failure"]],
        on=["asset_id", "date"],
        how="left"
    )
    base["binary_failure_30d"] = base["binary_failure_30d"].fillna(0).astype(int)

    # Final cleaning
    base = base.fillna(base.median(numeric_only=True))

    # Drop non-feature columns
    drop_cols = ["id", "created_at"]
    base = base.drop(columns=[c for c in drop_cols if c in base.columns])

    logger.success(f"Feature matrix complete: {len(base)} rows × {len(base.columns)} columns")
    logger.info(f"  Positive labels (failure within 30d): {base['binary_failure_30d'].sum()} "
                f"({base['binary_failure_30d'].mean()*100:.1f}%)")
    logger.info(f"  Feature columns: {len([c for c in base.columns if c not in ['asset_id','date','binary_failure_30d','max_severity_30d','days_to_next_failure']])}")

    return base


if __name__ == "__main__":
    df = build_full_feature_matrix()
    print(df.head())
    print(f"\nShape: {df.shape}")
    print(f"Label distribution:\n{df['binary_failure_30d'].value_counts()}")
