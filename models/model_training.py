"""
ORPMI Predictive Maintenance Model Training Pipeline
======================================================
Trains two complementary models:
  1. Random Forest Classifier   — interpretable, feature importance, robust
  2. Gradient Boosting (XGBoost-style via sklearn) — higher accuracy

Both are calibrated with Platt scaling to produce reliable probabilities.
The final model selection is based on ROC-AUC on the held-out test set.

Model outputs per asset per day:
  - failure_probability_30d  (calibrated probability 0–1)
  - risk_level               (Low / Medium / High / Critical)
  - maintenance_priority_score (risk-based composite)
  - top contributing features (top-3 SHAP-equivalent importances)
  - recommended action        (decision rule → human-readable text)
"""

import sys
import json
import pickle
import warnings
from pathlib import Path
from datetime import datetime

import numpy as np
import pandas as pd
from loguru import logger
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.calibration import CalibratedClassifierCV
from sklearn.model_selection import StratifiedKFold, cross_val_score
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import (
    roc_auc_score, precision_score, recall_score, f1_score,
    average_precision_score, confusion_matrix, classification_report
)
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer

warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config.settings import ASSET_REGISTRY

MODEL_DIR = Path(__file__).resolve().parent / "artifacts"
MODEL_DIR.mkdir(parents=True, exist_ok=True)

RANDOM_STATE = 42
TEST_SPLIT_DATE = "2024-10-01"   # Last quarter = test set (temporal split)

# Features to exclude from training (identifiers and targets)
EXCLUDE_COLS = {
    "asset_id", "date", "record_date",
    "binary_failure_30d", "max_severity_30d", "days_to_next_failure",
    "id", "created_at",
}


def temporal_train_test_split(df: pd.DataFrame):
    """
    Temporal split — train on Jan–Sep, test on Oct–Dec.
    Critical: never use future data to predict the past.
    Standard practice in industrial time-series ML.
    """
    df["date"] = pd.to_datetime(df["date"])
    train = df[df["date"] < TEST_SPLIT_DATE].copy()
    test  = df[df["date"] >= TEST_SPLIT_DATE].copy()
    logger.info(f"Train: {len(train)} rows | Test: {len(test)} rows")
    logger.info(f"Train positives: {train['binary_failure_30d'].sum()} "
                f"({train['binary_failure_30d'].mean()*100:.1f}%)")
    logger.info(f"Test positives: {test['binary_failure_30d'].sum()} "
                f"({test['binary_failure_30d'].mean()*100:.1f}%)")
    return train, test


def get_feature_cols(df: pd.DataFrame) -> list:
    return [c for c in df.columns if c not in EXCLUDE_COLS]


def build_rf_pipeline() -> Pipeline:
    """
    Random Forest pipeline with imputation.
    Advantages: handles missing values, provides feature importance,
    robust to outliers (common in industrial sensor data).
    Class_weight='balanced' handles the 78/22 class imbalance.
    """
    return Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("clf", RandomForestClassifier(
            n_estimators=200,
            max_depth=8,
            min_samples_leaf=5,
            class_weight="balanced",
            random_state=RANDOM_STATE,
            n_jobs=-1,
        ))
    ])


def build_gb_pipeline() -> Pipeline:
    """
    Gradient Boosting pipeline.
    Advantages: typically higher AUC than RF, captures non-linear
    interactions between sensor readings and failure history features.
    """
    return Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("clf", GradientBoostingClassifier(
            n_estimators=150,
            max_depth=4,
            learning_rate=0.05,
            subsample=0.8,
            min_samples_leaf=5,
            random_state=RANDOM_STATE,
        ))
    ])


def evaluate_model(model, X_test: pd.DataFrame, y_test: pd.Series, name: str) -> dict:
    """Comprehensive model evaluation metrics."""
    y_prob = model.predict_proba(X_test)[:, 1]
    y_pred = (y_prob >= 0.40).astype(int)   # Threshold 0.4: recall-optimised for safety

    roc_auc   = roc_auc_score(y_test, y_prob)
    avg_prec  = average_precision_score(y_test, y_prob)
    precision = precision_score(y_test, y_pred, zero_division=0)
    recall    = recall_score(y_test, y_pred, zero_division=0)
    f1        = f1_score(y_test, y_pred, zero_division=0)
    cm        = confusion_matrix(y_test, y_pred)

    results = {
        "model_name":      name,
        "roc_auc":         round(roc_auc, 4),
        "avg_precision":   round(avg_prec, 4),
        "precision":       round(precision, 4),
        "recall":          round(recall, 4),
        "f1_score":        round(f1, 4),
        "confusion_matrix": cm.tolist(),
        "tn": int(cm[0][0]), "fp": int(cm[0][1]),
        "fn": int(cm[1][0]), "tp": int(cm[1][1]),
        "threshold": 0.40,
    }

    logger.success(f"  [{name}] ROC-AUC={roc_auc:.4f} | "
                   f"Prec={precision:.3f} | Recall={recall:.3f} | F1={f1:.3f}")
    return results


def extract_feature_importance(model: Pipeline, feature_cols: list, top_n: int = 20) -> pd.DataFrame:
    """Extract and rank feature importances from the fitted model."""
    try:
        clf = model.named_steps["clf"]
    except AttributeError:
        clf = model.estimator if hasattr(model, "estimator") else model
    if hasattr(clf, "feature_importances_"):
        importances = clf.feature_importances_
    else:
        return pd.DataFrame()

    fi_df = pd.DataFrame({
        "feature": feature_cols,
        "importance": importances,
    }).sort_values("importance", ascending=False).head(top_n)
    fi_df["importance_pct"] = (fi_df["importance"] / fi_df["importance"].sum() * 100).round(2)
    return fi_df


def score_asset_latest(model: Pipeline, feature_matrix: pd.DataFrame) -> pd.DataFrame:
    """
    Score the latest record for each asset.
    Returns failure probability, risk level, and top contributing features.
    This is what feeds the Phase 3 dashboard page.
    """
    feature_cols = get_feature_cols(feature_matrix)
    feature_matrix["date"] = pd.to_datetime(feature_matrix["date"])

    # Latest record per asset
    latest = feature_matrix.sort_values("date").groupby("asset_id").last().reset_index()
    X_latest = latest[feature_cols]
    probs = model.predict_proba(X_latest)[:, 1]

    fi_df = extract_feature_importance(model, feature_cols, top_n=len(feature_cols))
    top_features = fi_df.head(3)["feature"].tolist() if not fi_df.empty else []

    results = []
    for i, (_, row) in enumerate(latest.iterrows()):
        prob = float(probs[i])
        asset_id = row["asset_id"]
        asset_info = ASSET_REGISTRY[asset_id]

        # Risk classification
        if prob >= 0.65:   risk_level = "Critical"
        elif prob >= 0.40: risk_level = "High"
        elif prob >= 0.20: risk_level = "Medium"
        else:              risk_level = "Low"

        # Priority score (risk-based)
        priority = (
            asset_info["criticality_score"] * 15 +
            prob * 35 +
            asset_info["downtime_cost_usd_per_hr"] / 2000
        )

        # Recommended action
        action = _recommend_action(prob, risk_level, row, asset_id)

        # Contributing factors (top features with values)
        contributing = []
        for feat in top_features[:3]:
            if feat in row.index:
                val = row[feat]
                contributing.append(f"{feat}={val:.2f}")

        results.append({
            "asset_id":                  asset_id,
            "asset_name":                asset_info["name"],
            "criticality":               asset_info["criticality"],
            "failure_probability_30d":   round(prob, 4),
            "risk_level_ml":             risk_level,
            "maintenance_priority_ml":   round(priority, 1),
            "recommended_action":        action,
            "contributing_factors":      " | ".join(contributing),
            "score_date":                row["date"].strftime("%Y-%m-%d"),
        })

    return pd.DataFrame(results).sort_values("maintenance_priority_ml", ascending=False)


def _recommend_action(prob: float, risk_level: str, row, asset_id: str) -> str:
    """
    Generate operational maintenance recommendation from model output.
    Language matches what a reliability engineer would write in a work order.
    """
    asset_name = ASSET_REGISTRY[asset_id]["name"]
    days_since_pm = row.get("days_since_last_pm", 0)
    vib = row.get("vibration_current", 0)
    overhaul_frac = row.get("overhaul_fraction", 0)

    if risk_level == "Critical":
        return (f"IMMEDIATE ACTION REQUIRED — {asset_name} shows {prob*100:.0f}% failure probability "
                f"within 30 days. Mobilise maintenance team for inspection. "
                f"Review last PM records and raise emergency work order.")
    elif risk_level == "High":
        horizon = "14 days" if prob >= 0.50 else "21 days"
        return (f"Schedule inspection within {horizon} — {asset_name} risk elevated. "
                f"Verify vibration trend, check seal condition. "
                f"Ensure next PM is not deferred.")
    elif risk_level == "Medium":
        return (f"Monitor closely — {asset_name} within acceptable range but trending. "
                f"Confirm PM scheduled within {int(days_since_pm)} days. "
                f"Review vibration readings at next operator round.")
    else:
        return (f"{asset_name} operating within normal parameters. "
                f"Continue routine PM schedule. No intervention required.")


def train_and_evaluate() -> dict:
    """Master training function — runs full pipeline end-to-end."""
    logger.info("=" * 60)
    logger.info("ORPMI Predictive Maintenance Model Training — START")
    logger.info("=" * 60)

    # Load feature matrix
    feat_path = Path(__file__).resolve().parent.parent / "data" / "processed" / "ml_feature_matrix.csv"
    if not feat_path.exists():
        logger.info("Feature matrix not found — building...")
        from models.feature_engineering import build_full_feature_matrix
        df = build_full_feature_matrix()
        df.to_csv(feat_path, index=False)
    else:
        df = pd.read_csv(feat_path)
        logger.info(f"Feature matrix loaded: {df.shape}")

    # Temporal split
    train_df, test_df = temporal_train_test_split(df)
    feature_cols = get_feature_cols(df)

    X_train = train_df[feature_cols]
    y_train = train_df["binary_failure_30d"]
    X_test  = test_df[feature_cols]
    y_test  = test_df["binary_failure_30d"]

    logger.info(f"Features: {len(feature_cols)}")

    # ── Train Random Forest ───────────────────────────────────────────────
    logger.info("\nTraining Random Forest...")
    rf_pipe = build_rf_pipeline()
    rf_calibrated = CalibratedClassifierCV(rf_pipe, method="isotonic", cv=3)
    rf_calibrated.fit(X_train, y_train)

    # ── Cross-validation ──────────────────────────────────────────────────
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=RANDOM_STATE)
    rf_cv_scores = cross_val_score(rf_pipe, X_train, y_train,
                                   cv=cv, scoring="roc_auc", n_jobs=-1)
    logger.info(f"  RF Cross-val ROC-AUC: {rf_cv_scores.mean():.4f} ± {rf_cv_scores.std():.4f}")

    # ── Train Gradient Boosting ───────────────────────────────────────────
    logger.info("Training Gradient Boosting...")
    gb_pipe = build_gb_pipeline()
    gb_calibrated = CalibratedClassifierCV(gb_pipe, method="isotonic", cv=3)
    gb_calibrated.fit(X_train, y_train)

    gb_cv_scores = cross_val_score(gb_pipe, X_train, y_train,
                                   cv=cv, scoring="roc_auc", n_jobs=-1)
    logger.info(f"  GB Cross-val ROC-AUC: {gb_cv_scores.mean():.4f} ± {gb_cv_scores.std():.4f}")

    # ── Evaluate on test set ──────────────────────────────────────────────
    logger.info("\nEvaluating on held-out test set (Oct–Dec 2024)...")
    rf_results = evaluate_model(rf_calibrated, X_test, y_test, "RandomForest")
    gb_results = evaluate_model(gb_calibrated, X_test, y_test, "GradientBoosting")

    # ── Select champion model ─────────────────────────────────────────────
    champion = rf_calibrated if rf_results["roc_auc"] >= gb_results["roc_auc"] else gb_calibrated
    champion_name = "RandomForest" if rf_results["roc_auc"] >= gb_results["roc_auc"] else "GradientBoosting"
    champion_results = rf_results if champion_name == "RandomForest" else gb_results
    logger.success(f"\n  Champion model: {champion_name} "
                   f"(ROC-AUC={champion_results['roc_auc']:.4f})")

    # ── Feature importance ────────────────────────────────────────────────
    # Extract from the inner (uncalibrated) estimator
    inner_pipe = champion.calibrated_classifiers_[0].estimator
    fi_df = extract_feature_importance(inner_pipe, feature_cols)
    logger.info(f"\n  Top 10 features:")
    for _, row in fi_df.head(10).iterrows():
        logger.info(f"    {row['feature']:<45} {row['importance_pct']:.2f}%")

    # ── Asset-level scores ────────────────────────────────────────────────
    asset_scores = score_asset_latest(champion, df)
    logger.info(f"\n  Asset risk scores:")
    for _, row in asset_scores.iterrows():
        logger.info(f"    {row['asset_id']}: {row['failure_probability_30d']*100:.1f}% — {row['risk_level_ml']}")

    # ── Save artefacts ────────────────────────────────────────────────────
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    model_path = MODEL_DIR / "champion_model.pkl"
    with open(model_path, "wb") as f:
        pickle.dump(champion, f)
    logger.success(f"  Champion model saved: {model_path}")

    fi_path = MODEL_DIR / "feature_importance.csv"
    fi_df.to_csv(fi_path, index=False)

    scores_path = MODEL_DIR / "asset_risk_scores.csv"
    asset_scores.to_csv(scores_path, index=False)

    # Model metadata JSON
    metadata = {
        "training_timestamp":      timestamp,
        "champion_model":          champion_name,
        "feature_count":           len(feature_cols),
        "training_rows":           len(train_df),
        "test_rows":               len(test_df),
        "train_period":            f"2024-01-01 to {TEST_SPLIT_DATE}",
        "test_period":             f"{TEST_SPLIT_DATE} to 2024-12-31",
        "positive_rate_train":     round(float(y_train.mean()), 4),
        "positive_rate_test":      round(float(y_test.mean()), 4),
        "rf_cv_roc_auc":           round(float(rf_cv_scores.mean()), 4),
        "gb_cv_roc_auc":           round(float(gb_cv_scores.mean()), 4),
        "champion_test_roc_auc":   champion_results["roc_auc"],
        "champion_precision":      champion_results["precision"],
        "champion_recall":         champion_results["recall"],
        "champion_f1":             champion_results["f1_score"],
        "champion_confusion_matrix": champion_results["confusion_matrix"],
        "rf_results":              rf_results,
        "gb_results":              gb_results,
        "top_10_features":         fi_df.head(10)[["feature","importance_pct"]].to_dict("records"),
        "asset_risk_scores":       asset_scores.to_dict("records"),
        "threshold":               0.40,
    }

    meta_path = MODEL_DIR / "model_metadata.json"
    with open(meta_path, "w") as f:
        json.dump(metadata, f, indent=2, default=str)
    logger.success(f"  Metadata saved: {meta_path}")

    logger.info("=" * 60)
    logger.success("Model training COMPLETE")
    logger.info("=" * 60)

    return metadata


if __name__ == "__main__":
    results = train_and_evaluate()
    print(f"\nChampion: {results['champion_model']}")
    print(f"ROC-AUC:  {results['champion_test_roc_auc']}")
    print(f"Recall:   {results['champion_recall']}")
    print(f"F1:       {results['champion_f1']}")
