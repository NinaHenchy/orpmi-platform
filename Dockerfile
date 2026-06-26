FROM python:3.11-slim

LABEL description="ORPMI Platform — Operational Reliability & Predictive Maintenance Intelligence"

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt

COPY . .
RUN mkdir -p data/raw data/processed data/exports database logs models/artifacts

ENV PYTHONPATH=/app
ENV STREAMLIT_SERVER_PORT=8501
ENV STREAMLIT_SERVER_ADDRESS=0.0.0.0
ENV STREAMLIT_SERVER_HEADLESS=true
ENV STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=10s --start-period=180s --retries=3 \
    CMD curl -f http://localhost:8501/_stcore/health || exit 1

RUN chmod +x scripts/docker_entrypoint.sh
ENTRYPOINT ["bash", "scripts/docker_entrypoint.sh"]
