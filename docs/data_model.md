# ORPMI Data Model — Field Definitions & Reliability Engineering Rationale

## Asset Operating Data — Field Justification

| Field | Type | Reliability Significance |
|---|---|---|
| `operating_hours_daily` | REAL | Feeds cumulative runtime → drives overhaul scheduling. Every asset has an OEM-specified overhaul interval in hours. |
| `operating_hours_cumulative` | REAL | Tracks life consumption. At 80% of overhaul interval, maintenance planning team initiates scope preparation. |
| `downtime_hours_daily` | REAL | Primary input for Availability KPI = (Runtime / Calendar Time). Every hour of unplanned downtime costs $9,500–$31,000 USD on this facility. |
| `vibration_mm_s` | REAL | ISO 10816 severity zones. Zone C (4.5–7.1 mm/s) = restricted operation. Zone D (>7.1 mm/s) = shutdown required. Leading indicator: vibration exceedances predict bearing/seal failures 10–30 days in advance. |
| `operating_temp_c` | REAL | Process deviation detection. Overtemperature accelerates seal and bearing degradation. Trending above design temp by >5°C triggers investigation. |
| `operating_pressure_bar` | REAL | Overpressure events trigger safety relief valve actuation and mandatory inspection. Chronic over-pressure indicates process control issue. |
| `efficiency_pct` | REAL | Gradual efficiency loss is the signature of pump wear ring degradation, compressor valve wear, and heat exchanger fouling — detectable weeks before catastrophic failure. |
| `flow_rate_m3h` | REAL | Deviation from rated flow indicates blockage, wear, or pump degradation. Operators use this to detect fouling in heat exchangers and separator internals. |

## Failure Events — Field Justification

| Field | Type | Reliability Significance |
|---|---|---|
| `failure_category` | VARCHAR | ISO 14224 taxonomy. Enables FMEA, Pareto analysis of dominant failure modes. Drives targeted PM improvements. |
| `failure_severity` | VARCHAR | Critical failures = full production loss. Minor failures = degraded operation. Severity drives whether a corrective work order is raised as emergency or planned. |
| `downtime_hours` | REAL | Direct financial impact input. Multiplied by asset-specific downtime cost rate to compute production deferral cost. |
| `time_to_repair_hrs` | REAL | MTTR input. Measures maintenance workforce effectiveness. Benchmarked against industry targets. High MTTR indicates parts availability issues or skill gaps. |
| `time_to_detect_hrs` | REAL | Mean Delay Time (MDT). The gap between failure occurrence and detection. High MDT indicates poor condition monitoring coverage or insufficient operator rounds frequency. |
| `root_cause` | TEXT | RCFA (Root Cause Failure Analysis) outcome. Required for eliminating recurring failures. Populates the facility's Bad Actor register. |
| `is_recurrence` | INTEGER | Identifies chronic vs one-off failures. Recurring failures on same asset/mode trigger engineering review and PM scope revision. |

## KPI Daily Summary — Computation Logic

| KPI | Formula | Target | Business Impact |
|---|---|---|---|
| `availability_pct` | (Runtime hrs / Calendar hrs) × 100 | ≥97% | 1% availability loss = ~$2.2M/year on this facility |
| `reliability_score` | Weighted composite: availability (45%) + inspection score (25%) + maintenance compliance (20%) + MTBF index (10%) | ≥85 | Single score for ranking assets in executive reports |
| `mtbf_hrs` | (Total Runtime − Total Downtime) / Failure Count (90-day rolling) | ≥720 hrs | Low MTBF = asset is a Bad Actor consuming disproportionate maintenance spend |
| `mttr_hrs` | Mean of time_to_repair_hrs (90-day rolling) | ≤8 hrs | High MTTR = slow response, spares unavailability, or inadequate maintenance procedures |
| `health_score` | Composite: availability, inspection score, MTBF, compliance | ≥80 | Primary indicator for maintenance priority ranking. Red (<60) = action required |
| `failure_probability_30d` | Heuristic (Phase 1), ML-refined (Phase 3) | <0.20 | Predictive score used to trigger proactive maintenance before failure occurs |
| `maintenance_priority_score` | Criticality × 15 + (100 − health) × 0.5 + fail_prob × 20 + cost_factor | Higher = higher priority | Objective basis for maintenance work order prioritisation replacing subjective decision-making |
