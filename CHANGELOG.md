# Changelog

All notable changes to the ORPMI Platform are documented in this file.
Format follows [Keep a Changelog](https://keepachangelog.com/).

---

## [4.0.0] — 2024-12-31 — Executive Operations Platform

### Added
- Complete test suite: 76 tests across 9 test classes (100% pass rate)
- Technical architecture documentation (`docs/technical_architecture.md`)
- Data model field definitions with reliability engineering rationale (`docs/data_model.md`)
- MIT License
- Full GitHub Actions CI/CD: ETL → ML Training → 76 Tests → Docker Build
- Production README with badges, architecture summary, and quick start
- `CHANGELOG.md` — formal release history

### Infrastructure
- Docker multi-stage build verified
- GitHub Actions workflow covers all four pipeline stages
- All 76 pytest tests passing on clean environment

---

## [3.0.0] — 2024-11-30 — Predictive Maintenance Intelligence

### Added
- Feature engineering pipeline: 80 features across 5 groups
  - Sensor statistics (rolling 7d/14d/30d windows)
  - Degradation slope features (vib_slope_14d, vib_slope_30d — dominant predictors)
  - Maintenance history features (days since PM, compliance rate, corrective frequency)
  - Failure recency features (rolling failure counts, severity weighting)
  - KPI trajectory features (availability slope, health trend)
- ML training pipeline: Random Forest + Gradient Boosting with Isotonic calibration
- Temporal train/test split: Jan–Sep 2024 (train), Oct–Dec 2024 (test)
- **Champion model: Random Forest — ROC-AUC 0.9381**
- Risk scoring engine with operational recommendation generation
- AI narrative generator (natural language asset status per asset)
- Page 8: Predictive Maintenance Intelligence dashboard
- Page 9: Executive Operations Intelligence dashboard
- `scripts/train_models.py` — one-command ML pipeline runner

### Model Metrics
- ROC-AUC: 0.9381 (test set)
- Recall: 0.294
- F1 Score: 0.454
- Top feature: vib_slope_14d (17.4% importance)

---

## [2.0.0] — 2024-10-31 — Reliability Analytics Dashboard

### Added
- 7-page Streamlit dashboard with dark industrial theme
- Page 1: Operations Overview — executive fleet summary, financial impact
- Page 2: Reliability Scorecard — MTBF/MTTR, availability trends, ranking
- Page 3: Downtime Analysis — cost Pareto, monthly trend, severity distribution
- Page 4: Maintenance Performance — PM compliance, work order register
- Page 5: Asset Health Monitor — health gauges, risk heatmap, priority matrix
- Page 6: Sensor Trends — ISO 10816 vibration zones, efficiency degradation
- Page 7: Failure Analysis — Pareto, bad actor register, RCFA log
- Centralised data access layer (16 parameterised SQL query functions)
- Plotly-based dark industrial theme engine
- `.streamlit/config.toml` for consistent theming

---

## [1.0.0] — 2024-09-30 — Industrial Data Foundation

### Added
- 7-table SQLite schema aligned to ISO 14224 petroleum equipment taxonomy
  - `assets` — master equipment registry
  - `asset_operating_data` — daily sensor readings
  - `failure_events` — failure history with RCFA fields
  - `maintenance_records` — PM and corrective work orders
  - `inspection_records` — NDT and condition assessment records
  - `downtime_log` — granular downtime with production impact
  - `kpi_daily_summary` — pre-computed daily KPI aggregations
- 3 SQL views: asset current status, monthly KPI rollup, failure Pareto
- Physics-based synthetic data generator for 6 production assets
- 29-check data validation framework (sensor physics, referential integrity, domain rules)
- KPI computation engine: availability, MTBF, MTTR, health score, risk level
- ETL orchestrator with run logging and validation reporting
- Docker deployment files (Dockerfile, docker-compose.yml)
- GitHub Actions CI pipeline
