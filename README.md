# ORPMI Platform
### Operational Reliability & Predictive Maintenance Intelligence

> **Production-grade industrial analytics platform for Oil & Gas production facility operations.**
> Designed to the operational standard of Shell, Chevron, ExxonMobil, TotalEnergies, Seplat Energy, NNPC, SLB, and Baker Hughes environments.

[![Python 3.11](https://img.shields.io/badge/Python-3.11-blue?logo=python)](https://python.org)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.35-red?logo=streamlit)](https://streamlit.io)
[![SQLite](https://img.shields.io/badge/Database-SQLite%20%7C%20PostgreSQL-blue?logo=sqlite)](https://sqlite.org)
[![Docker](https://img.shields.io/badge/Docker-Ready-blue?logo=docker)](https://docker.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-green)](LICENSE)

---

## Platform Overview

The ORPMI Platform transforms fragmented operational data into decision-ready intelligence across four capability layers:

| Layer | Capability | Audience |
|---|---|---|
| **Data Foundation** | ISO 14224 asset database, ETL pipeline, 29-check validation | Data Engineer |
| **Reliability Analytics** | MTBF, MTTR, availability, downtime cost, maintenance compliance | Reliability Engineer |
| **Predictive Intelligence** | ML failure probability (ROC-AUC 0.9381), risk scoring, maintenance recommendations | Maintenance Superintendent |
| **Executive Reporting** | Fleet KPIs, AI narratives, financial impact, operational risk register | Operations Director |

---

## Live Demo

🔗 **[Launch Platform →](https://orpmi-platform.streamlit.app)** *(Streamlit Cloud)*

---

## Monitored Assets — OPC-Alpha Facility

| Asset ID | Asset Name | Type | Criticality | Downtime Cost/hr |
|---|---|---|---|---|
| **P-101** | Crude Transfer Pump | Centrifugal Pump | 🔴 Critical | $18,500 |
| **P-202** | Export Pump | Centrifugal Pump | 🔴 Critical | $24,000 |
| **C-201** | Gas Compressor | Reciprocating Compressor | 🔴 Critical | $31,000 |
| **TK-105** | Crude Storage Tank | Fixed Roof Tank | 🟡 High | $12,000 |
| **HX-401** | Heat Exchanger | Shell & Tube | 🟡 High | $9,500 |
| **V-301** | Three-Phase Separator | Pressure Vessel | 🔴 Critical | $28,000 |

---

## Dashboard Pages

| Page | Title | Key Visualisations |
|---|---|---|
| 1 | **Operations Overview** | Fleet KPIs, asset status table, monthly trend, risk matrix, financial impact |
| 2 | **Reliability Scorecard** | MTBF/MTTR comparison, availability trend, reliability ranking |
| 3 | **Downtime Analysis** | Downtime Pareto, monthly trend, severity distribution, event log |
| 4 | **Maintenance Performance** | PM compliance, cost by type, work order register |
| 5 | **Asset Health Monitor** | Health gauges, risk heatmap, priority matrix, inspection scores |
| 6 | **Sensor Trends** | ISO 10816 vibration zones, temp/pressure trend, efficiency degradation |
| 7 | **Failure Analysis** | Failure Pareto, bad actor register, timeline, RCFA log |
| 8 | **Predictive Maintenance** | ML failure gauges, probability trend, feature importance, confusion matrix |
| 9 | **Executive Intelligence** | Fleet radar, AI narratives, risk register, cost breakdown |

---

## ML Model Performance

| Metric | Value | Benchmark |
|---|---|---|
| **ROC-AUC** | **0.9381** | Excellent ≥ 0.85 |
| Recall | 0.294 | Failure capture rate |
| F1 Score | 0.454 | Precision/recall balance |
| Features | 80 engineered | Sensor + history + KPIs |
| Train Period | Jan–Sep 2024 | Temporal split |
| Test Period | Oct–Dec 2024 | No data leakage |

**Top predictive signals:** vibration slope (14-day), vibration slope (30-day), vibration current — consistent with ISO 10816 reliability theory.

---

## Quick Start

```bash
# Clone repository
git clone https://github.com/YOUR_USERNAME/orpmi-platform.git
cd orpmi-platform

# Install dependencies
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Initialise database and run ETL
python scripts/setup_database.py

# Train predictive maintenance model
python scripts/train_models.py

# Launch dashboard
streamlit run dashboards/app.py
```

---

## Docker Deployment

```bash
# Build and run
docker build -t orpmi-platform:latest .
docker-compose up -d

# Access at http://localhost:8501
```

---

## Project Structure

```
orpmi/
├── config/                      # Platform and asset configuration
│   └── settings.py              # Asset registry, KPI thresholds, facility params
├── data/
│   ├── raw/                     # Source data (gitignored)
│   ├── processed/               # ETL output CSVs + ML feature matrix
│   └── exports/                 # Dashboard exports
├── database/
│   ├── schemas/orpmi_schema.sql # 7-table DDL (ISO 14224 aligned)
│   └── db_connection.py         # SQLite/PostgreSQL connection manager
├── etl/
│   ├── extractors/              # Synthetic industrial data generator
│   ├── validators/              # 29-check data validation framework
│   ├── loaders/                 # Database write operations
│   └── run_etl.py               # Master ETL orchestrator
├── models/
│   ├── feature_engineering.py  # 5-group, 80-feature engineering pipeline
│   ├── model_training.py        # RF + GB, calibration, temporal CV, evaluation
│   ├── risk_scoring_engine.py   # Production inference + recommendation engine
│   └── artifacts/               # Trained model + metadata (gitignored)
├── dashboards/
│   ├── app.py                   # Streamlit entry point + navigation
│   ├── data_access.py           # Centralised SQL query layer (16 functions)
│   ├── components/              # Dark theme + Plotly engine
│   └── pages/                   # 9 dashboard page modules
├── tests/                       # Unit and integration tests
├── docs/                        # Technical documentation
├── scripts/
│   ├── setup_database.py        # One-command database setup
│   └── train_models.py          # One-command ML pipeline
├── .github/workflows/           # GitHub Actions CI
├── Dockerfile                   # Production container
└── docker-compose.yml           # Multi-container orchestration
```

---

## Technology Stack

| Layer | Technology |
|---|---|
| **Language** | Python 3.11 |
| **Database** | SQLite (dev) · PostgreSQL (prod) |
| **ETL** | Pandas · SQLAlchemy · Custom validation framework |
| **ML** | Scikit-Learn · CalibratedClassifierCV · Isotonic calibration |
| **Dashboard** | Streamlit 1.35 · Plotly 5.22 |
| **Deployment** | Docker · Streamlit Cloud |
| **CI/CD** | GitHub Actions |
| **Standard** | ISO 14224 · ISO 10816 |

---

## Industrial Relevance

This platform demonstrates:

- **Asset Performance Management (APM)** — health scoring, criticality ranking, KPI tracking
- **Reliability Centred Maintenance (RCM)** — MTBF/MTTR analysis, failure mode taxonomy
- **Predictive Maintenance (PdM)** — ML failure probability, leading indicator monitoring
- **Risk-Based Inspection (RBI)** — corrosion rates, inspection scoring, fitness-for-service
- **Operational Excellence** — maintenance compliance, downtime cost, PM scheduling
- **Executive Reporting** — fleet KPIs, financial impact, AI-generated narratives

---

## Business Value

| Outcome | Mechanism |
|---|---|
| Reduce unplanned downtime | 30-day failure probability alerts enable proactive intervention |
| Improve maintenance planning | Risk-based priority scores replace subjective work order scheduling |
| Financial impact visibility | Per-asset downtime cost tracking ($9,500–$31,000/hr) |
| Maintenance compliance | PM schedule adherence monitoring with overdue flagging |
| Executive decision support | Fleet radar, AI narratives, risk register in one view |

---

## Release History

| Release | Title | Key Deliverables |
|---|---|---|
| **v1.0** | Industrial Data Foundation | 7-table schema, ETL pipeline, 29-check validation, KPI engine |
| **v2.0** | Reliability Analytics Dashboard | 7-page Streamlit dashboard, dark industrial theme |
| **v3.0** | Predictive Maintenance Intelligence | ML model (ROC-AUC 0.9381), risk scoring, AI narratives |
| **v4.0** | Executive Operations Platform | Test suite, production docs, Docker CI/CD, full release |

---

## License

MIT License — see [LICENSE](LICENSE)

---

*ORPMI Platform — Built for industrial operations professionals transitioning into analytics.*
*Demonstrates practical operational intelligence capability for Oil & Gas, Energy, and Industrial sectors.*
