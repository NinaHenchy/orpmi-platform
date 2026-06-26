# ORPMI Platform — Technical Architecture

## System Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                    ORPMI PLATFORM ARCHITECTURE                       │
└─────────────────────────────────────────────────────────────────────┘

┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐
│   DATA SOURCES   │    │   ETL PIPELINE   │    │    DATABASE      │
│                  │    │                  │    │                  │
│  Sensor Feeds    │───▶│  Extract         │───▶│  SQLite (dev)    │
│  SCADA/DCS       │    │  Validate (29✓)  │    │  PostgreSQL (prod)│
│  CMMS Export     │    │  Transform       │    │                  │
│  Inspection Data │    │  Load            │    │  7 Tables        │
└──────────────────┘    └──────────────────┘    │  3 Views         │
                                                │  6 Indexes       │
                                                └────────┬─────────┘
                                                         │
                        ┌────────────────────────────────▼──────────┐
                        │           ML PIPELINE                      │
                        │                                            │
                        │  Feature Engineering (80 features)         │
                        │  ├── Sensor Statistics (rolling windows)   │
                        │  ├── Degradation Slopes (14d, 30d)         │
                        │  ├── Maintenance History                   │
                        │  ├── Failure Recency                       │
                        │  └── KPI Trajectory                        │
                        │                                            │
                        │  Model Training                            │
                        │  ├── Random Forest (champion: AUC 0.9381)  │
                        │  ├── Gradient Boosting (challenger)        │
                        │  ├── Isotonic Calibration                  │
                        │  └── Temporal Split (no data leakage)      │
                        │                                            │
                        │  Risk Scoring Engine                       │
                        │  ├── Failure Probability (0–1)             │
                        │  ├── Risk Classification (4 levels)        │
                        │  ├── Maintenance Priority Score            │
                        │  └── AI Narrative Generation               │
                        └────────────────────────────────┬───────────┘
                                                         │
                        ┌────────────────────────────────▼──────────┐
                        │         STREAMLIT DASHBOARD (9 pages)      │
                        │                                            │
                        │  Data Access Layer (16 SQL functions)      │
                        │  Dark Industrial Theme (Plotly engine)     │
                        │                                            │
                        │  Page 1: Operations Overview               │
                        │  Page 2: Reliability Scorecard             │
                        │  Page 3: Downtime Analysis                 │
                        │  Page 4: Maintenance Performance           │
                        │  Page 5: Asset Health Monitor              │
                        │  Page 6: Sensor Trends                     │
                        │  Page 7: Failure Analysis                  │
                        │  Page 8: Predictive Maintenance            │
                        │  Page 9: Executive Intelligence            │
                        └────────────────────────────────────────────┘
```

---

## Database Schema (ISO 14224 Aligned)

### Table: assets
Master equipment registry. Single source of truth for all asset parameters used in KPI computation, risk scoring, and cost calculations.

| Column | Type | Purpose |
|---|---|---|
| asset_id | PK | Unique identifier (P-101, C-201 etc.) |
| criticality | VARCHAR | Critical/High/Medium/Low |
| criticality_score | INT | 1–5 numeric for ML features |
| downtime_cost_usd_per_hr | REAL | Financial impact rate — drives cost calculations |
| pm_interval_days | INT | Preventive maintenance schedule interval |
| overhaul_interval_hrs | INT | Major overhaul trigger threshold |
| target_availability_pct | REAL | KPI target for RAG scoring |

### Table: asset_operating_data
Time-series sensor readings per asset per day. Primary source for ML feature engineering.

| Column | Reliability Significance |
|---|---|
| vibration_mm_s | ISO 10816 zones: 0–2.3 Normal, 2.3–4.5 Satisfactory, 4.5–7.1 Alarm, >7.1 Shutdown |
| operating_temp_c | Overtemperature precedes seal/bearing failure |
| efficiency_pct | Gradual decline = wear signature. Rate of decline > static value for prediction |
| downtime_hours_daily | Direct input to Availability KPI |

### Table: kpi_daily_summary
Pre-computed daily KPI aggregations. Avoids expensive re-computation at dashboard query time.

Key computed fields:
- `availability_pct` = (Runtime / Calendar hrs) × 100
- `health_score` = weighted composite (availability 40% + inspection 30% + MTBF 20% + compliance 10%)
- `failure_probability_30d` = Phase 1 heuristic, replaced by ML model in Phase 3
- `maintenance_priority_score` = criticality × 15 + (100 − health) × 0.5 + fail_prob × 20 + cost_factor

---

## ML Feature Groups

### Group 1: Sensor Statistics (rolling windows: 7d, 14d, 30d)
Rolling mean, max, std, P95 of vibration, temperature, pressure, efficiency.
**Reliability rationale:** Point-in-time readings are noisy. Rolling aggregates capture trend direction and sustained exceedances.

### Group 2: Degradation Slopes
Linear regression slope of vibration, temperature, and efficiency over 14-day and 30-day windows.
**Reliability rationale:** The rate of parameter change is more predictive than its absolute value. A rising vibration slope indicates bearing wear progression.

### Group 3: Maintenance History
Days since last PM, PM compliance rate (90d), corrective maintenance frequency.
**Reliability rationale:** Overdue PMs directly correlate with elevated failure probability. Corrective maintenance frequency indicates an asset entering a bad-actor cycle.

### Group 4: Failure Recency
Failures in last 30/60/90/180 days, days since last failure, severity-weighted failure score.
**Reliability rationale:** Recent failures indicate unresolved root causes and elevated recurrence probability.

### Group 5: KPI Trajectory
30-day slope of availability and health score, MTBF current value, compliance current value.
**Reliability rationale:** Declining KPI trajectories precede failure events even when absolute values are still acceptable.

---

## KPI Definitions (ISO 14224 Aligned)

| KPI | Formula | Industry Standard |
|---|---|---|
| Availability | (Operating hrs / Calendar hrs) × 100 | ISO 14224 §12 |
| MTBF | (Total Runtime − Downtime) / Failure Count | ISO 14224 §12 |
| MTTR | Mean of repair duration across all failures | ISO 14224 §12 |
| Health Score | Weighted composite (availability + inspection + MTBF + compliance) | Internal |
| Failure Probability | Calibrated RF model output | ML |
| Maintenance Priority | Risk-based composite score | Internal |

---

## Production Deployment Architecture

```
Development:
  SQLite DB → Local Streamlit → localhost:8501

Staging:
  Docker Container → docker-compose → localhost:8501

Production:
  PostgreSQL → Docker → Cloud Platform (Render/Railway/AWS ECS)
  URL: https://orpmi.yourcompany.com
  Auth: Streamlit secrets + OAuth (Phase 5 roadmap)

CI/CD:
  GitHub push → GitHub Actions → ETL test → pytest 76 tests → deploy
```

---

## Technology Decisions

| Decision | Choice | Rationale |
|---|---|---|
| DB: SQLite vs PostgreSQL | SQLite (dev), PG (prod) | Zero infrastructure for development; one env var change to upgrade |
| ML: RF vs XGBoost | Random Forest | Interpretable feature importance; robust to sensor outliers; faster training |
| Calibration: Platt vs Isotonic | Isotonic | More flexible for non-linear probability output; better for imbalanced data |
| Train/Test: Random vs Temporal | Temporal | Prevents data leakage; mirrors real deployment where future is unknown |
| Dashboard: Streamlit vs Dash | Streamlit | Faster development; native Python; better for analyst-built tools |
| Theme: Light vs Dark | Dark industrial | Matches operator console environments; reduces eye strain on 12hr shifts |
