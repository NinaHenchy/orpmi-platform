#!/bin/bash
set -e
echo "ORPMI Platform starting..."
cd /app
export PYTHONPATH=/app

if [ ! -f "database/orpmi_dev.db" ]; then
    echo "Initialising database..."
    python scripts/setup_database.py
fi

if [ ! -f "models/artifacts/champion_model.pkl" ]; then
    echo "Training ML model..."
    python scripts/train_models.py
fi

echo "Launching Streamlit on port 8501..."
exec streamlit run dashboards/app.py \
    --server.port=8501 \
    --server.address=0.0.0.0 \
    --server.headless=true \
    --browser.gatherUsageStats=false
