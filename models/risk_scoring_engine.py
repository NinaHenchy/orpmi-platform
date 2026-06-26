"""
ORPMI Risk Scoring Engine
==========================
Production inference wrapper for the trained predictive maintenance model.
Used by the Phase 3 dashboard pages and can be called by scheduled jobs.

Provides:
  - load_model()                  — loads the champion model from disk
  - score_all_assets()            — generates current risk scores for all 6 assets
  - get_maintenance_recommendations()  — structured recommendation objects
  - get_ai_narrative()            — natural language operations summary per asset
  - load_model_metadata()         — training metrics, feature importances
"""

import sys
import json
import pickle
import warnings
from pathlib import Path
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
from loguru import logger

warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config.settings import ASSET_REGISTRY, KPI_THRESHOLDS

MODEL_DIR = Path(__file__).resolve().parent / "artifacts"
PROCESSED_DIR = Path(__file__).resolve().parent.parent / "data" / "processed"


def load_model():
    """Load the champion model from disk. Returns None if not yet trained."""
    model_path = MODEL_DIR / "champion_model.pkl"
    if not model_path.exists():
        logger.warning("Champion model not found. Run model_training.py first.")
        return None
    with open(model_path, "rb") as f:
        model = pickle.load(f)
    logger.info("Champion model loaded.")
    return model


def load_model_metadata() -> dict:
    """Load training run metadata and evaluation metrics."""
    meta_path = MODEL_DIR / "model_metadata.json"
    if not meta_path.exists():
        return {}
    with open(meta_path) as f:
        return json.load(f)


def load_feature_importance() -> pd.DataFrame:
    """Load feature importance rankings from training run."""
    fi_path = MODEL_DIR / "feature_importance.csv"
    if not fi_path.exists():
        return pd.DataFrame()
    return pd.read_csv(fi_path)


def score_all_assets() -> pd.DataFrame:
    """
    Score all assets using the latest feature data.
    Returns enriched risk score DataFrame ready for dashboard consumption.
    Falls back to pre-computed scores if model is unavailable.
    """
    # Try pre-computed scores first (from last training run)
    scores_path = MODEL_DIR / "asset_risk_scores.csv"
    if scores_path.exists():
        scores = pd.read_csv(scores_path)
        logger.info(f"Risk scores loaded from disk: {len(scores)} assets")
        return _enrich_scores(scores)

    # Fall back: compute from feature matrix
    feat_path = PROCESSED_DIR / "ml_feature_matrix.csv"
    if not feat_path.exists():
        logger.warning("Feature matrix not found — returning heuristic scores")
        return _heuristic_fallback_scores()

    model = load_model()
    if model is None:
        return _heuristic_fallback_scores()

    from models.model_training import get_feature_cols, score_asset_latest
    df = pd.read_csv(feat_path)
    scores = score_asset_latest(model, df)
    return _enrich_scores(scores)


def _enrich_scores(scores: pd.DataFrame) -> pd.DataFrame:
    """Add additional context fields to the score DataFrame."""
    scores = scores.copy()

    # Add replacement cost and downtime cost from registry
    scores["replacement_cost_usd"]      = scores["asset_id"].map(
        {k: v["replacement_cost_usd"] for k, v in ASSET_REGISTRY.items()}
    )
    scores["downtime_cost_usd_per_hr"]  = scores["asset_id"].map(
        {k: v["downtime_cost_usd_per_hr"] for k, v in ASSET_REGISTRY.items()}
    )
    scores["area"]                       = scores["asset_id"].map(
        {k: v["area"] for k, v in ASSET_REGISTRY.items()}
    )
    scores["system_name"]                = scores["asset_id"].map(
        {k: v["system"] for k, v in ASSET_REGISTRY.items()}
    )

    # Expected cost if failure occurs
    scores["expected_failure_cost_usd"] = (
        scores["failure_probability_30d"] *
        scores["downtime_cost_usd_per_hr"] * 24   # avg 24hr downtime assumption
    ).round(0)

    return scores


def _heuristic_fallback_scores() -> pd.DataFrame:
    """Emergency fallback if model artefacts are missing."""
    rows = []
    for asset_id, info in ASSET_REGISTRY.items():
        import random
        random.seed(hash(asset_id) % 100)
        prob = round(random.uniform(0.15, 0.65), 3)
        risk = "Critical" if prob >= 0.65 else "High" if prob >= 0.40 else "Medium" if prob >= 0.20 else "Low"
        rows.append({
            "asset_id": asset_id,
            "asset_name": info["name"],
            "criticality": info["criticality"],
            "failure_probability_30d": prob,
            "risk_level_ml": risk,
            "maintenance_priority_ml": info["criticality_score"] * 15 + prob * 35,
            "recommended_action": f"Review {info['name']} — heuristic risk assessment pending model deployment.",
            "contributing_factors": "Model not available",
            "score_date": datetime.now().strftime("%Y-%m-%d"),
        })
    return pd.DataFrame(rows)


def get_maintenance_recommendations() -> list:
    """
    Returns structured maintenance recommendation objects.
    Sorted by maintenance priority score descending.
    """
    scores = score_all_assets()
    recommendations = []

    for _, row in scores.sort_values("maintenance_priority_ml", ascending=False).iterrows():
        prob = float(row["failure_probability_30d"])
        asset_id = row["asset_id"]
        asset_info = ASSET_REGISTRY[asset_id]
        risk = row.get("risk_level_ml", "Medium")

        # Urgency window
        if risk == "Critical":
            urgency_days = 3
            urgency_label = "IMMEDIATE (3 days)"
        elif risk == "High":
            urgency_days = 14
            urgency_label = "URGENT (14 days)"
        elif risk == "Medium":
            urgency_days = 30
            urgency_label = "SCHEDULED (30 days)"
        else:
            urgency_days = 90
            urgency_label = "ROUTINE (next cycle)"

        recommendations.append({
            "asset_id":           asset_id,
            "asset_name":         asset_info["name"],
            "asset_type":         asset_info["type"],
            "criticality":        asset_info["criticality"],
            "risk_level":         risk,
            "failure_probability":prob,
            "priority_score":     float(row.get("maintenance_priority_ml", 0)),
            "urgency_label":      urgency_label,
            "urgency_days":       urgency_days,
            "recommended_action": row.get("recommended_action", "Review asset condition."),
            "contributing_factors": row.get("contributing_factors", ""),
            "expected_cost_if_fail": float(row.get("expected_failure_cost_usd", 0)),
            "downtime_cost_per_hr":  asset_info["downtime_cost_usd_per_hr"],
        })

    return recommendations


def get_ai_narrative(asset_id: str = None) -> dict:
    """
    Generates natural language operational narratives per asset.
    These appear in the Executive Intelligence page — pre-computed
    summaries that a non-technical executive can act on immediately.

    Format modelled on Reliability Engineer shift handover language.
    """
    scores = score_all_assets()
    from database.db_connection import get_engine
    from sqlalchemy import text
    engine = get_engine()

    narratives = {}

    for _, row in scores.iterrows():
        aid = row["asset_id"]
        if asset_id and aid != asset_id:
            continue

        prob = float(row["failure_probability_30d"])
        risk = row.get("risk_level_ml", "Medium")
        asset_info = ASSET_REGISTRY[aid]

        # Pull recent failure count
        try:
            with engine.connect() as conn:
                fail_count = conn.execute(text(
                    f"SELECT COUNT(*) FROM failure_events WHERE asset_id='{aid}'"
                )).scalar()
                last_fail = conn.execute(text(
                    f"SELECT MAX(failure_date) FROM failure_events WHERE asset_id='{aid}'"
                )).scalar()
                total_dt = conn.execute(text(
                    f"SELECT SUM(downtime_hours) FROM failure_events WHERE asset_id='{aid}'"
                )).scalar() or 0
        except Exception:
            fail_count, last_fail, total_dt = 0, None, 0

        pct_str = f"{prob*100:.0f}%"
        dt_cost  = total_dt * asset_info["downtime_cost_usd_per_hr"]

        # Compose narrative
        if risk == "Critical":
            narrative = (
                f"{aid} — {asset_info['name']} has reached critical risk status with a "
                f"{pct_str} modelled failure probability over the next 30 days. "
                f"Year-to-date, this asset has recorded {fail_count} failure event(s) "
                f"accumulating {total_dt:.1f} downtime hours and ${dt_cost:,.0f} in associated costs. "
                f"Immediate maintenance intervention is recommended. "
                f"Escalate to Maintenance Superintendent and Reliability Engineer for same-day review."
            )
        elif risk == "High":
            narrative = (
                f"{aid} — {asset_info['name']} is operating at elevated risk ({pct_str} failure probability). "
                f"The predictive model has identified {row.get('contributing_factors','vibration and thermal trends')} "
                f"as primary risk drivers. "
                f"This asset has experienced {fail_count} failure(s) YTD with ${dt_cost:,.0f} in downtime costs. "
                f"Maintenance inspection is recommended within 14 days. "
                f"Review last PM completion and verify vibration readings at next operator round."
            )
        elif risk == "Medium":
            narrative = (
                f"{aid} — {asset_info['name']} is within acceptable operating parameters "
                f"with a {pct_str} modelled failure probability. "
                f"YTD performance: {fail_count} failure event(s), {total_dt:.1f} downtime hours. "
                f"Continue scheduled PM program. No immediate intervention required, "
                f"but monitor condition trends at the next inspection."
            )
        else:
            narrative = (
                f"{aid} — {asset_info['name']} is performing well. "
                f"Failure probability stands at {pct_str} — below the Medium risk threshold. "
                f"No unplanned failures YTD is the target; current trend is favourable. "
                f"Continue routine monitoring and maintain PM schedule adherence."
            )

        narratives[aid] = {
            "asset_id":             aid,
            "asset_name":           asset_info["name"],
            "risk_level":           risk,
            "failure_probability":  prob,
            "narrative":            narrative,
            "failure_count_ytd":    fail_count,
            "downtime_hrs_ytd":     total_dt,
            "downtime_cost_ytd":    dt_cost,
        }

    return narratives


if __name__ == "__main__":
    scores = score_all_assets()
    print("\nAsset Risk Scores:")
    print(scores[["asset_id","asset_name","failure_probability_30d",
                  "risk_level_ml","maintenance_priority_ml"]].to_string(index=False))

    print("\nNarratives:")
    narratives = get_ai_narrative()
    for aid, n in narratives.items():
        print(f"\n{aid}: [{n['risk_level']}]")
        print(f"  {n['narrative'][:200]}...")
