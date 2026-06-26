"""
ORPMI Phase 3 — ML Training Pipeline Runner
Run this after setup_database.py to train the predictive maintenance model.
"""
import sys
from pathlib import Path
for _p in [str(Path(__file__).resolve().parent.parent), "/app"]:
    if _p not in sys.path:
        sys.path.insert(0, _p)



import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))


def main():
    print("=" * 60)
    print("ORPMI Phase 3 — Predictive Maintenance Model Training")
    print("=" * 60)

    # Step 1: Feature engineering
    print("\n[Step 1] Building feature matrix...")
    from models.feature_engineering import build_full_feature_matrix
    df = build_full_feature_matrix()
    out_path = BASE_DIR / "data" / "processed" / "ml_feature_matrix.csv"
    df.to_csv(out_path, index=False)
    print(f"  ✓ Feature matrix: {df.shape[0]} rows × {df.shape[1]} features")
    print(f"  ✓ Positive rate: {df['binary_failure_30d'].mean()*100:.1f}%")

    # Step 2: Model training
    print("\n[Step 2] Training models...")
    from models.model_training import train_and_evaluate
    metadata = train_and_evaluate()
    print(f"  ✓ Champion: {metadata['champion_model']}")
    print(f"  ✓ ROC-AUC:  {metadata['champion_test_roc_auc']:.4f}")
    print(f"  ✓ Recall:   {metadata['champion_recall']:.3f}")
    print(f"  ✓ F1 Score: {metadata['champion_f1']:.3f}")

    # Step 3: Verify scoring engine
    print("\n[Step 3] Verifying risk scoring engine...")
    from models.risk_scoring_engine import score_all_assets
    scores = score_all_assets()
    print(f"  ✓ Scored {len(scores)} assets")
    for _, row in scores.iterrows():
        print(f"      {row['asset_id']}: {row['failure_probability_30d']*100:.1f}% — {row['risk_level_ml']}")

    print("\n" + "=" * 60)
    print("✅ Phase 3 ML Pipeline Complete")
    print(f"   Model artefacts saved to: models/artifacts/")
    print(f"   Launch dashboard: streamlit run dashboards/app.py")
    print("=" * 60)


if __name__ == "__main__":
    main()
