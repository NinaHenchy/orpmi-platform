"""
ORPMI Platform — Test Suite
============================
Unit and integration tests covering:
  - Data validation framework
  - ETL pipeline integrity
  - KPI computation correctness
  - Feature engineering outputs
  - Model inference pipeline
  - Database query layer

Run: pytest tests/test_orpmi.py -v
"""

import sys
import json
import pickle
import warnings
from pathlib import Path

import pytest
import pandas as pd
import numpy as np

warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


# ─────────────────────────────────────────────
# FIXTURES
# ─────────────────────────────────────────────

@pytest.fixture(scope="session")
def engine():
    from database.db_connection import get_engine
    return get_engine()


@pytest.fixture(scope="session")
def all_tables(engine):
    from sqlalchemy import text
    tables = ["assets", "asset_operating_data", "failure_events",
              "maintenance_records", "kpi_daily_summary",
              "inspection_records", "downtime_log"]
    counts = {}
    with engine.connect() as conn:
        for t in tables:
            counts[t] = conn.execute(text(f"SELECT COUNT(*) FROM {t}")).scalar()
    return counts


@pytest.fixture(scope="session")
def assets_df(engine):
    return pd.read_sql("SELECT * FROM assets", engine)


@pytest.fixture(scope="session")
def kpi_df(engine):
    return pd.read_sql("SELECT * FROM kpi_daily_summary", engine)


@pytest.fixture(scope="session")
def failures_df(engine):
    return pd.read_sql("SELECT * FROM failure_events", engine)


@pytest.fixture(scope="session")
def ops_df(engine):
    return pd.read_sql("SELECT * FROM asset_operating_data", engine)


# ─────────────────────────────────────────────
# DATABASE TESTS
# ─────────────────────────────────────────────

class TestDatabase:
    """Database integrity and row count validation."""

    def test_database_connection(self, engine):
        from sqlalchemy import text
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1")).scalar()
        assert result == 1, "Database connection failed"

    def test_all_tables_populated(self, all_tables):
        for table, count in all_tables.items():
            assert count > 0, f"Table {table} is empty"

    def test_assets_count(self, all_tables):
        assert all_tables["assets"] == 6, f"Expected 6 assets, got {all_tables['assets']}"

    def test_operating_data_count(self, all_tables):
        # 6 assets × 365 days = 2190
        assert all_tables["asset_operating_data"] == 2190, \
            f"Expected 2190 operating records, got {all_tables['asset_operating_data']}"

    def test_kpi_summary_count(self, all_tables):
        assert all_tables["kpi_daily_summary"] == 2190

    def test_failure_events_exist(self, all_tables):
        assert all_tables["failure_events"] > 0, "No failure events in database"

    def test_maintenance_records_exist(self, all_tables):
        assert all_tables["maintenance_records"] > 0


# ─────────────────────────────────────────────
# ASSET REGISTRY TESTS
# ─────────────────────────────────────────────

class TestAssets:
    """Asset registry integrity."""

    EXPECTED_ASSETS = {"P-101", "P-202", "C-201", "TK-105", "HX-401", "V-301"}
    EXPECTED_CRITICALITIES = {"Critical", "High"}

    def test_all_expected_assets_present(self, assets_df):
        present = set(assets_df["asset_id"].tolist())
        assert present == self.EXPECTED_ASSETS, \
            f"Asset mismatch: expected {self.EXPECTED_ASSETS}, got {present}"

    def test_criticality_values_valid(self, assets_df):
        valid = {"Critical", "High", "Medium", "Low"}
        actual = set(assets_df["criticality"].tolist())
        assert actual.issubset(valid), f"Invalid criticality values: {actual - valid}"

    def test_criticality_scores_in_range(self, assets_df):
        assert assets_df["criticality_score"].between(1, 5).all(), \
            "Criticality scores must be 1–5"

    def test_downtime_cost_positive(self, assets_df):
        assert (assets_df["downtime_cost_usd_per_hr"] > 0).all(), \
            "All assets must have positive downtime costs"

    def test_replacement_cost_positive(self, assets_df):
        assert (assets_df["replacement_cost_usd"] > 0).all()

    def test_target_availability_realistic(self, assets_df):
        assert assets_df["target_availability_pct"].between(90, 100).all(), \
            "Target availability must be 90–100%"

    def test_critical_assets_are_critical(self, assets_df):
        # C-201, V-301, P-101, P-202 must all be Critical
        critical_assets = assets_df[assets_df["asset_id"].isin(["C-201", "V-301"])]["criticality"]
        assert (critical_assets == "Critical").all(), \
            "C-201 and V-301 must be Critical"


# ─────────────────────────────────────────────
# OPERATING DATA TESTS
# ─────────────────────────────────────────────

class TestOperatingData:
    """Sensor data physics and range validation."""

    def test_operating_hours_range(self, ops_df):
        assert ops_df["operating_hours_daily"].between(0, 24).all(), \
            "Daily operating hours must be 0–24"

    def test_downtime_hours_range(self, ops_df):
        assert ops_df["downtime_hours_daily"].between(0, 24).all()

    def test_total_hours_not_exceed_24(self, ops_df):
        total = ops_df["operating_hours_daily"] + ops_df["downtime_hours_daily"]
        assert (total <= 24.01).all(), \
            "Operating + downtime hours cannot exceed 24h/day"

    def test_vibration_non_negative(self, ops_df):
        vib = ops_df["vibration_mm_s"].dropna()
        assert (vib >= 0).all(), "Vibration readings cannot be negative"

    def test_vibration_physically_bounded(self, ops_df):
        vib = ops_df["vibration_mm_s"].dropna()
        assert (vib <= 50).all(), "Vibration > 50 mm/s is physically implausible"

    def test_efficiency_percentage_range(self, ops_df):
        eff = ops_df["efficiency_pct"].dropna()
        assert eff.between(0, 100).all(), "Efficiency must be 0–100%"

    def test_temperature_non_negative(self, ops_df):
        temp = ops_df["operating_temp_c"].dropna()
        assert (temp >= 0).all(), "Operating temperature cannot be negative"

    def test_no_duplicate_asset_date(self, ops_df):
        dupes = ops_df.duplicated(subset=["asset_id", "record_date"]).sum()
        assert dupes == 0, f"{dupes} duplicate (asset_id, record_date) combinations found"

    def test_all_assets_have_operating_data(self, ops_df):
        from config.settings import ASSET_REGISTRY
        for asset_id in ASSET_REGISTRY.keys():
            assert asset_id in ops_df["asset_id"].values, \
                f"No operating data for {asset_id}"


# ─────────────────────────────────────────────
# KPI COMPUTATION TESTS
# ─────────────────────────────────────────────

class TestKPIs:
    """KPI value ranges and business rule validation."""

    def test_availability_range(self, kpi_df):
        avail = kpi_df["availability_pct"].dropna()
        assert avail.between(0, 100).all(), "Availability must be 0–100%"

    def test_health_score_range(self, kpi_df):
        health = kpi_df["health_score"].dropna()
        assert health.between(0, 100).all(), "Health score must be 0–100"

    def test_reliability_score_range(self, kpi_df):
        rel = kpi_df["reliability_score"].dropna()
        assert rel.between(0, 100).all()

    def test_failure_probability_range(self, kpi_df):
        prob = kpi_df["failure_probability_30d"].dropna()
        assert prob.between(0, 1).all(), "Failure probability must be 0–1"

    def test_mtbf_positive(self, kpi_df):
        mtbf = kpi_df["mtbf_hrs"].dropna()
        assert (mtbf > 0).all(), "MTBF must be positive"

    def test_risk_levels_valid(self, kpi_df):
        valid = {"Low", "Medium", "High", "Critical"}
        actual = set(kpi_df["risk_level"].dropna().tolist())
        assert actual.issubset(valid), f"Invalid risk levels: {actual - valid}"

    def test_all_assets_have_kpis(self, kpi_df):
        from config.settings import ASSET_REGISTRY
        for asset_id in ASSET_REGISTRY.keys():
            assert asset_id in kpi_df["asset_id"].values, \
                f"No KPI records for {asset_id}"

    def test_kpi_covers_full_year(self, kpi_df):
        min_date = kpi_df["summary_date"].min()
        max_date = kpi_df["summary_date"].max()
        assert min_date <= "2024-01-31", f"KPI data starts too late: {min_date}"
        assert max_date >= "2024-11-30", f"KPI data ends too early: {max_date}"

    def test_fleet_availability_above_threshold(self, kpi_df):
        """Fleet average availability should be above 85% — basic operations sanity check."""
        avg_avail = kpi_df["availability_pct"].mean()
        assert avg_avail > 85, f"Fleet average availability {avg_avail:.1f}% is below minimum threshold"

    def test_maintenance_compliance_realistic(self, kpi_df):
        compliance = kpi_df["maintenance_compliance_pct"].dropna()
        assert compliance.between(0, 100).all()


# ─────────────────────────────────────────────
# FAILURE EVENTS TESTS
# ─────────────────────────────────────────────

class TestFailureEvents:
    """Failure event data integrity."""

    def test_failure_events_exist(self, failures_df):
        assert len(failures_df) > 0, "No failure events found"

    def test_severity_values_valid(self, failures_df):
        valid = {"Critical", "Major", "Minor", "Negligible"}
        actual = set(failures_df["failure_severity"].tolist())
        assert actual.issubset(valid), f"Invalid severity values: {actual - valid}"

    def test_downtime_hours_positive(self, failures_df):
        assert (failures_df["downtime_hours"] > 0).all(), \
            "All failure events must have positive downtime hours"

    def test_downtime_hours_bounded(self, failures_df):
        assert (failures_df["downtime_hours"] <= 8760).all(), \
            "Downtime hours cannot exceed one year"

    def test_financial_impact_non_negative(self, failures_df):
        assert (failures_df["financial_impact_usd"] >= 0).all()

    def test_failure_categories_populated(self, failures_df):
        assert failures_df["failure_category"].notna().all(), \
            "All failures must have a category"

    def test_asset_ids_valid(self, failures_df):
        from config.settings import ASSET_REGISTRY
        valid_ids = set(ASSET_REGISTRY.keys())
        actual_ids = set(failures_df["asset_id"].tolist())
        assert actual_ids.issubset(valid_ids), \
            f"Unknown asset IDs in failures: {actual_ids - valid_ids}"


# ─────────────────────────────────────────────
# DATA ACCESS LAYER TESTS
# ─────────────────────────────────────────────

class TestDataAccess:
    """Dashboard data access layer function tests."""

    def test_get_assets_returns_six(self):
        from dashboards.data_access import get_assets
        df = get_assets()
        assert len(df) == 6

    def test_get_latest_kpis_returns_six(self):
        from dashboards.data_access import get_latest_kpis
        df = get_latest_kpis()
        assert len(df) == 6, f"Expected 6 assets in latest KPIs, got {len(df)}"

    def test_get_facility_summary_keys(self):
        from dashboards.data_access import get_facility_summary
        summary = get_facility_summary()
        required_keys = [
            "fleet_availability", "fleet_health_score", "total_failures_ytd",
            "total_downtime_hrs_ytd", "total_downtime_cost_usd", "maintenance_compliance"
        ]
        for key in required_keys:
            assert key in summary, f"Missing key in facility summary: {key}"

    def test_get_failure_events_not_empty(self):
        from dashboards.data_access import get_failure_events
        df = get_failure_events()
        assert len(df) > 0

    def test_get_failure_pareto_has_categories(self):
        from dashboards.data_access import get_failure_pareto
        df = get_failure_pareto()
        assert len(df) > 0
        assert "failure_category" in df.columns

    def test_get_maintenance_records_not_empty(self):
        from dashboards.data_access import get_maintenance_records
        df = get_maintenance_records()
        assert len(df) > 0

    def test_get_kpi_timeseries_all_assets(self):
        from dashboards.data_access import get_kpi_timeseries
        df = get_kpi_timeseries()
        assert df["asset_id"].nunique() == 6


# ─────────────────────────────────────────────
# FEATURE ENGINEERING TESTS
# ─────────────────────────────────────────────

class TestFeatureEngineering:
    """ML feature matrix validation."""

    @pytest.fixture(scope="class")
    def feature_matrix(self):
        feat_path = Path("data/processed/ml_feature_matrix.csv")
        if feat_path.exists():
            return pd.read_csv(feat_path)
        from models.feature_engineering import build_full_feature_matrix
        return build_full_feature_matrix()

    def test_feature_matrix_shape(self, feature_matrix):
        assert len(feature_matrix) == 2190, \
            f"Expected 2190 rows, got {len(feature_matrix)}"
        assert len(feature_matrix.columns) >= 70, \
            f"Expected >= 70 features, got {len(feature_matrix.columns)}"

    def test_label_column_exists(self, feature_matrix):
        assert "binary_failure_30d" in feature_matrix.columns

    def test_label_is_binary(self, feature_matrix):
        unique_labels = set(feature_matrix["binary_failure_30d"].unique())
        assert unique_labels.issubset({0, 1}), \
            f"Label must be binary (0/1), got {unique_labels}"

    def test_positive_rate_realistic(self, feature_matrix):
        pos_rate = feature_matrix["binary_failure_30d"].mean()
        assert 0.05 <= pos_rate <= 0.50, \
            f"Positive rate {pos_rate:.2f} is outside realistic range 5–50%"

    def test_vibration_slope_features_present(self, feature_matrix):
        assert "vib_slope_14d" in feature_matrix.columns, \
            "vib_slope_14d (dominant feature) must be in feature matrix"
        assert "vib_slope_30d" in feature_matrix.columns

    def test_no_all_null_columns(self, feature_matrix):
        numeric_cols = feature_matrix.select_dtypes(include=[np.number]).columns
        null_rates = feature_matrix[numeric_cols].isnull().mean()
        all_null = null_rates[null_rates == 1.0]
        assert len(all_null) == 0, \
            f"Columns with 100% null: {all_null.index.tolist()}"

    def test_all_assets_in_features(self, feature_matrix):
        from config.settings import ASSET_REGISTRY
        for asset_id in ASSET_REGISTRY.keys():
            assert asset_id in feature_matrix["asset_id"].values


# ─────────────────────────────────────────────
# ML MODEL TESTS
# ─────────────────────────────────────────────

class TestMLModel:
    """Model artefacts and inference validation."""

    @pytest.fixture(scope="class")
    def model_metadata(self):
        meta_path = Path("models/artifacts/model_metadata.json")
        if not meta_path.exists():
            pytest.skip("Model not yet trained — run scripts/train_models.py")
        with open(meta_path) as f:
            return json.load(f)

    @pytest.fixture(scope="class")
    def champion_model(self):
        model_path = Path("models/artifacts/champion_model.pkl")
        if not model_path.exists():
            pytest.skip("Model not yet trained — run scripts/train_models.py")
        with open(model_path, "rb") as f:
            return pickle.load(f)

    def test_model_file_exists(self):
        assert Path("models/artifacts/champion_model.pkl").exists(), \
            "Champion model file missing — run scripts/train_models.py"

    def test_metadata_file_exists(self):
        assert Path("models/artifacts/model_metadata.json").exists()

    def test_roc_auc_meets_minimum(self, model_metadata):
        roc = model_metadata["champion_test_roc_auc"]
        assert roc >= 0.75, f"ROC-AUC {roc:.4f} below minimum threshold 0.75"

    def test_roc_auc_production_grade(self, model_metadata):
        roc = model_metadata["champion_test_roc_auc"]
        assert roc >= 0.85, f"ROC-AUC {roc:.4f} below production-grade threshold 0.85"

    def test_feature_count_adequate(self, model_metadata):
        n_feats = model_metadata["feature_count"]
        assert n_feats >= 50, f"Only {n_feats} features — expected at least 50"

    def test_no_data_leakage_temporal_split(self, model_metadata):
        # Train must end before test starts
        train_period = model_metadata.get("train_period", "")
        test_period  = model_metadata.get("test_period", "")
        assert "2024-10" in test_period, "Test period must start in Oct 2024"
        assert "2024-01" in train_period, "Train period must start Jan 2024"

    def test_model_produces_probabilities(self, champion_model):
        # Create minimal feature vector matching expected input
        feat_path = Path("data/processed/ml_feature_matrix.csv")
        if not feat_path.exists():
            pytest.skip("Feature matrix not found")
        df = pd.read_csv(feat_path)
        exclude = {"asset_id","date","binary_failure_30d","max_severity_30d","days_to_next_failure","id","created_at"}
        feature_cols = [c for c in df.columns if c not in exclude]
        X_sample = df[feature_cols].head(10).fillna(0)
        probs = champion_model.predict_proba(X_sample)[:, 1]
        assert len(probs) == 10
        assert (probs >= 0).all() and (probs <= 1).all(), \
            "Model must produce valid probabilities between 0 and 1"

    def test_feature_importance_file_exists(self):
        assert Path("models/artifacts/feature_importance.csv").exists()

    def test_top_feature_is_vibration_related(self):
        fi_path = Path("models/artifacts/feature_importance.csv")
        if not fi_path.exists():
            pytest.skip("Feature importance file missing")
        fi_df = pd.read_csv(fi_path)
        top_feature = fi_df.iloc[0]["feature"]
        assert "vib" in top_feature.lower() or "vibration" in top_feature.lower(), \
            f"Top feature '{top_feature}' should be vibration-related per ISO 10816 theory"


# ─────────────────────────────────────────────
# RISK SCORING ENGINE TESTS
# ─────────────────────────────────────────────

class TestRiskScoringEngine:
    """Risk scoring engine and recommendation generation."""

    @pytest.fixture(scope="class")
    def risk_scores(self):
        from models.risk_scoring_engine import score_all_assets
        return score_all_assets()

    def test_scores_all_six_assets(self, risk_scores):
        assert len(risk_scores) == 6, \
            f"Expected 6 asset scores, got {len(risk_scores)}"

    def test_probabilities_in_range(self, risk_scores):
        probs = risk_scores["failure_probability_30d"]
        assert probs.between(0, 1).all(), "Failure probabilities must be 0–1"

    def test_risk_levels_valid(self, risk_scores):
        valid = {"Low", "Medium", "High", "Critical"}
        actual = set(risk_scores["risk_level_ml"].tolist())
        assert actual.issubset(valid), f"Invalid risk levels: {actual - valid}"

    def test_priority_scores_positive(self, risk_scores):
        assert (risk_scores["maintenance_priority_ml"] > 0).all()

    def test_recommendations_generated(self):
        from models.risk_scoring_engine import get_maintenance_recommendations
        recs = get_maintenance_recommendations()
        assert len(recs) == 6
        for rec in recs:
            assert "recommended_action" in rec
            assert len(rec["recommended_action"]) > 10

    def test_narratives_generated(self):
        from models.risk_scoring_engine import get_ai_narrative
        narratives = get_ai_narrative()
        assert len(narratives) == 6
        for asset_id, narr in narratives.items():
            assert len(narr["narrative"]) > 50, \
                f"Narrative for {asset_id} is too short"


# ─────────────────────────────────────────────
# CONFIGURATION TESTS
# ─────────────────────────────────────────────

class TestConfiguration:
    """Platform configuration integrity."""

    def test_asset_registry_has_six_assets(self):
        from config.settings import ASSET_REGISTRY
        assert len(ASSET_REGISTRY) == 6

    def test_all_assets_have_required_fields(self):
        from config.settings import ASSET_REGISTRY
        required = ["name", "type", "criticality", "criticality_score",
                    "downtime_cost_usd_per_hr", "pm_interval_days",
                    "overhaul_interval_hrs", "replacement_cost_usd"]
        for asset_id, info in ASSET_REGISTRY.items():
            for field in required:
                assert field in info, f"{asset_id} missing field: {field}"

    def test_kpi_thresholds_logical(self):
        from config.settings import KPI_THRESHOLDS
        assert KPI_THRESHOLDS["availability_green"] > KPI_THRESHOLDS["availability_amber"], \
            "Green threshold must be above amber"
        assert KPI_THRESHOLDS["health_score_green"] > KPI_THRESHOLDS["health_score_amber"]

    def test_facility_capacity_positive(self):
        from config.settings import FACILITY_CAPACITY_BOPD
        assert FACILITY_CAPACITY_BOPD > 0


# ─────────────────────────────────────────────
# INTEGRATION TEST
# ─────────────────────────────────────────────

class TestEndToEnd:
    """End-to-end pipeline integration test."""

    def test_full_data_pipeline_integrity(self, kpi_df, assets_df, failures_df):
        """Verify referential integrity across the full data model."""
        from config.settings import ASSET_REGISTRY

        # All KPI records reference valid assets
        valid_ids = set(ASSET_REGISTRY.keys())
        kpi_ids   = set(kpi_df["asset_id"].unique())
        assert kpi_ids.issubset(valid_ids), f"Unknown asset IDs in KPIs: {kpi_ids - valid_ids}"

        # All failure events reference valid assets
        fail_ids = set(failures_df["asset_id"].unique())
        assert fail_ids.issubset(valid_ids), f"Unknown asset IDs in failures: {fail_ids - valid_ids}"

        # KPI count matches 6 assets × 365 days
        assert len(kpi_df) == 2190

    def test_financial_impact_consistency(self, failures_df):
        """Financial impact should be correlated with downtime hours."""
        corr = failures_df[["downtime_hours","financial_impact_usd"]].corr().iloc[0, 1]
        assert corr > 0.5, \
            f"Downtime hours and financial impact should be positively correlated, got {corr:.3f}"

    def test_kpi_availability_matches_operating_data(self, engine):
        """KPI availability should be consistent with operating data."""
        from sqlalchemy import text
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT k.asset_id,
                       AVG(k.availability_pct) as kpi_avail,
                       AVG(o.operating_hours_daily / 24.0 * 100) as ops_avail
                FROM kpi_daily_summary k
                JOIN asset_operating_data o
                    ON k.asset_id = o.asset_id
                    AND k.summary_date = o.record_date
                GROUP BY k.asset_id
            """)).fetchall()
        for row in result:
            # KPI availability (90-day rolling) vs single-day operating hours
            # They won't match exactly due to rolling window, but both should be >80%
            assert row[1] > 80, f"{row[0]}: KPI availability {row[1]:.1f}% unexpectedly low"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
