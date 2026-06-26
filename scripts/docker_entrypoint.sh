#!/bin/bash
set -e
cd /app
export PYTHONPATH=/app

echo "============================================================"
echo "ORPMI Platform Starting..."
echo "============================================================"

if [ ! -f "database/orpmi_dev.db" ]; then
    echo "Step 1/2: Initialising database..."
    python scripts/setup_database.py
    echo "Database ready."
fi

if [ ! -f "models/artifacts/champion_model.pkl" ]; then
    echo "Step 2/2: Training ML model..."
    python scripts/train_models.py
    echo "Model ready."
fi

echo "Launching Streamlit on port 8501..."
exec streamlit run dashboards/app.py \
    --server.port=8501 \
    --server.address=0.0.0.0 \
    --server.headless=true \
    --browser.gatherUsageStats=false