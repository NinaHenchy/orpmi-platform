-- =============================================================================
-- ORPMI Platform — Database Schema
-- Version: 1.0.0
-- Database: SQLite (dev) / PostgreSQL (prod)
-- Standard: ISO 14224 Petroleum and Natural Gas Industries — Data Collection
-- =============================================================================

-- -----------------------------------------------------------------------------
-- TABLE: assets
-- Purpose: Master asset registry — single source of truth for all monitored
--          equipment on the facility. Every operational record references this.
-- Reliability significance: Stores criticality scores, design limits, and cost
--          parameters that drive risk-based maintenance prioritisation.
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS assets (
    asset_id                VARCHAR(20)  PRIMARY KEY,
    asset_name              VARCHAR(120) NOT NULL,
    asset_type              VARCHAR(80)  NOT NULL,
    area                    VARCHAR(80)  NOT NULL,
    system_name             VARCHAR(120) NOT NULL,
    criticality             VARCHAR(20)  NOT NULL CHECK (criticality IN ('Critical','High','Medium','Low')),
    criticality_score       INTEGER      NOT NULL CHECK (criticality_score BETWEEN 1 AND 5),
    manufacturer            VARCHAR(80),
    model_number            VARCHAR(80),
    commission_year         INTEGER,
    design_pressure_bar     REAL,
    design_temp_c           REAL,
    rated_flow_m3h          REAL,
    replacement_cost_usd    REAL,
    downtime_cost_usd_per_hr REAL,
    pm_interval_days        INTEGER,
    overhaul_interval_hrs   INTEGER,
    target_availability_pct REAL,
    is_active               INTEGER      DEFAULT 1,
    created_at              TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
    updated_at              TIMESTAMP    DEFAULT CURRENT_TIMESTAMP
);

-- -----------------------------------------------------------------------------
-- TABLE: asset_operating_data
-- Purpose: Time-series operational parameters captured per asset per day.
--          This is the primary data source for KPI computation, trend analysis,
--          and the predictive maintenance model feature set.
-- Reliability significance:
--   - operating_hours_cumulative: drives MTBF and overhaul scheduling
--   - vibration_mm_s: leading indicator of bearing/seal degradation
--   - operating_temp_c / operating_pressure_bar: process deviation detection
--   - efficiency_pct: identifies gradual performance degradation before failure
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS asset_operating_data (
    id                          INTEGER      PRIMARY KEY AUTOINCREMENT,
    asset_id                    VARCHAR(20)  NOT NULL REFERENCES assets(asset_id),
    record_date                 DATE         NOT NULL,
    operating_hours_daily       REAL         NOT NULL DEFAULT 0,
    operating_hours_cumulative  REAL         NOT NULL DEFAULT 0,
    runtime_hours_ytd           REAL         NOT NULL DEFAULT 0,
    downtime_hours_daily        REAL         NOT NULL DEFAULT 0,
    downtime_hours_ytd          REAL         NOT NULL DEFAULT 0,
    operating_temp_c            REAL,
    operating_pressure_bar      REAL,
    vibration_mm_s              REAL,        -- ISO 10816 severity: <2.3=Good, 2.3-4.5=Satisfactory, 4.5-7.1=Unsatisfactory, >7.1=Unacceptable
    flow_rate_m3h               REAL,
    power_consumption_kw        REAL,
    efficiency_pct              REAL,
    is_running                  INTEGER      DEFAULT 1,
    created_at                  TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(asset_id, record_date)
);

-- -----------------------------------------------------------------------------
-- TABLE: failure_events
-- Purpose: Records every failure and unplanned stoppage per asset.
--          Foundation for MTBF, MTTR, failure frequency, and failure mode
--          analysis (FMEA) reporting.
-- Reliability significance:
--   - failure_category: enables Pareto analysis of dominant failure modes
--   - downtime_hours: directly feeds financial impact calculations
--   - time_to_repair_hrs (MTTR): measures maintenance workforce effectiveness
--   - recurrence flag: identifies chronic vs one-off failures
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS failure_events (
    id                      INTEGER      PRIMARY KEY AUTOINCREMENT,
    asset_id                VARCHAR(20)  NOT NULL REFERENCES assets(asset_id),
    failure_date            DATE         NOT NULL,
    failure_time            TIME,
    failure_category        VARCHAR(80)  NOT NULL,
    failure_description     TEXT,
    failure_severity        VARCHAR(20)  NOT NULL CHECK (failure_severity IN ('Critical','Major','Minor','Negligible')),
    detection_method        VARCHAR(60),           -- How was failure detected: Condition monitoring, Operator, Alarm
    downtime_hours          REAL         NOT NULL DEFAULT 0,
    time_to_repair_hrs      REAL,                  -- MTTR input
    time_to_detect_hrs      REAL,                  -- MDT: Mean Delay Time (reporting/logistics delay)
    production_loss_bbls    REAL,
    financial_impact_usd    REAL,
    root_cause              TEXT,
    corrective_action       TEXT,
    is_recurrence           INTEGER      DEFAULT 0,
    work_order_id           VARCHAR(30),
    reported_by             VARCHAR(60),
    closed_date             DATE,
    created_at              TIMESTAMP    DEFAULT CURRENT_TIMESTAMP
);

-- -----------------------------------------------------------------------------
-- TABLE: maintenance_records
-- Purpose: Full history of all maintenance activities — preventive, corrective,
--          and predictive. Feeds compliance KPIs and cost tracking.
-- Reliability significance:
--   - maintenance_type: separates reactive from proactive spend
--   - compliance_flag: whether PM was executed on schedule (±10% window)
--   - actual_cost_usd: enables maintenance cost per operating hour calculations
--   - next_due_date: drives forward maintenance scheduling and workload planning
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS maintenance_records (
    id                      INTEGER      PRIMARY KEY AUTOINCREMENT,
    asset_id                VARCHAR(20)  NOT NULL REFERENCES assets(asset_id),
    work_order_id           VARCHAR(30)  UNIQUE NOT NULL,
    maintenance_type        VARCHAR(60)  NOT NULL,
    maintenance_date        DATE         NOT NULL,
    scheduled_date          DATE,
    completion_date         DATE,
    maintenance_description TEXT,
    technician              VARCHAR(60),
    duration_hrs            REAL,
    parts_replaced          TEXT,
    estimated_cost_usd      REAL,
    actual_cost_usd         REAL,
    compliance_flag         INTEGER      DEFAULT 1,   -- 1=Compliant, 0=Overdue/Missed
    overdue_days            INTEGER      DEFAULT 0,
    next_due_date           DATE,
    failure_prevented       INTEGER      DEFAULT 0,   -- 1=PM avoided a failure (condition monitoring finding)
    inspection_score        REAL,                     -- Post-maintenance condition assessment 0–100
    notes                   TEXT,
    created_at              TIMESTAMP    DEFAULT CURRENT_TIMESTAMP
);

-- -----------------------------------------------------------------------------
-- TABLE: inspection_records
-- Purpose: Structured inspection data from physical walkthroughs, NDT surveys,
--          and condition monitoring rounds. Critical for Asset Integrity Mgmt.
-- Reliability significance:
--   - inspection_score: tracks asset condition over time (trending to failure)
--   - findings_count: early warning of deteriorating asset condition
--   - corrosion_rate_mm_yr: drives fitness-for-service and remaining life calcs
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS inspection_records (
    id                      INTEGER      PRIMARY KEY AUTOINCREMENT,
    asset_id                VARCHAR(20)  NOT NULL REFERENCES assets(asset_id),
    inspection_date         DATE         NOT NULL,
    inspection_type         VARCHAR(60)  NOT NULL,   -- Visual, NDT, Vibration Survey, Thermographic
    inspector_name          VARCHAR(60),
    inspection_score        REAL         NOT NULL CHECK (inspection_score BETWEEN 0 AND 100),
    overall_condition       VARCHAR(20)  NOT NULL CHECK (overall_condition IN ('Excellent','Good','Fair','Poor','Critical')),
    findings_count          INTEGER      DEFAULT 0,
    critical_findings       INTEGER      DEFAULT 0,
    corrosion_rate_mm_yr    REAL,
    wall_thickness_mm       REAL,
    next_inspection_date    DATE,
    action_required         INTEGER      DEFAULT 0,
    action_description      TEXT,
    report_reference        VARCHAR(30),
    created_at              TIMESTAMP    DEFAULT CURRENT_TIMESTAMP
);

-- -----------------------------------------------------------------------------
-- TABLE: kpi_daily_summary
-- Purpose: Pre-computed daily KPI snapshot per asset. Avoids recomputing
--          expensive aggregations at dashboard query time. Populated by ETL.
-- Reliability significance: Enables time-series trending of all primary KPIs
--          — the foundation for executive dashboards and management reporting.
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS kpi_daily_summary (
    id                          INTEGER      PRIMARY KEY AUTOINCREMENT,
    asset_id                    VARCHAR(20)  NOT NULL REFERENCES assets(asset_id),
    summary_date                DATE         NOT NULL,
    availability_pct            REAL,        -- (Runtime / Calendar Time) × 100
    reliability_score           REAL,        -- Composite: availability + MTBF + maintenance compliance
    mtbf_hrs                    REAL,        -- Mean Time Between Failures (rolling 90-day)
    mttr_hrs                    REAL,        -- Mean Time To Repair (rolling 90-day)
    downtime_hrs                REAL,        -- Total downtime for reporting period
    failure_count               INTEGER,     -- Number of failures in reporting period
    maintenance_compliance_pct  REAL,        -- % of PMs completed on schedule
    maintenance_cost_usd        REAL,        -- Total maintenance spend
    health_score                REAL,        -- ML-derived composite health index 0–100
    risk_level                  VARCHAR(20), -- Low / Medium / High / Critical
    failure_probability_30d     REAL,        -- ML model output
    maintenance_priority_score  REAL,        -- Risk-based priority ranking score
    created_at                  TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(asset_id, summary_date)
);

-- -----------------------------------------------------------------------------
-- TABLE: downtime_log
-- Purpose: Granular downtime records per event — start/stop timestamps,
--          cause classification, and production impact.
-- Reliability significance: Enables MTTR trend analysis and identifies
--          whether downtime is dominated by repair, logistics, or waiting time.
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS downtime_log (
    id                      INTEGER      PRIMARY KEY AUTOINCREMENT,
    asset_id                VARCHAR(20)  NOT NULL REFERENCES assets(asset_id),
    downtime_start          TIMESTAMP    NOT NULL,
    downtime_end            TIMESTAMP,
    downtime_hours          REAL,
    downtime_category       VARCHAR(60)  NOT NULL,  -- Equipment Failure, PM Shutdown, Awaiting Parts, Process Upset
    downtime_cause          TEXT,
    production_impact       VARCHAR(20)  CHECK (production_impact IN ('Full Loss','Partial','Derated','No Impact')),
    production_loss_bbls    REAL         DEFAULT 0,
    financial_impact_usd    REAL         DEFAULT 0,
    linked_failure_id       INTEGER      REFERENCES failure_events(id),
    linked_wo_id            VARCHAR(30),
    operator_on_duty        VARCHAR(60),
    created_at              TIMESTAMP    DEFAULT CURRENT_TIMESTAMP
);

-- -----------------------------------------------------------------------------
-- INDEXES — Query optimisation for dashboard response time
-- -----------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_aod_asset_date   ON asset_operating_data(asset_id, record_date);
CREATE INDEX IF NOT EXISTS idx_fe_asset_date    ON failure_events(asset_id, failure_date);
CREATE INDEX IF NOT EXISTS idx_mr_asset_date    ON maintenance_records(asset_id, maintenance_date);
CREATE INDEX IF NOT EXISTS idx_kpi_asset_date   ON kpi_daily_summary(asset_id, summary_date);
CREATE INDEX IF NOT EXISTS idx_dl_asset_start   ON downtime_log(asset_id, downtime_start);
CREATE INDEX IF NOT EXISTS idx_ir_asset_date    ON inspection_records(asset_id, inspection_date);

-- -----------------------------------------------------------------------------
-- VIEWS — Reusable query layers consumed by the dashboard and ETL
-- -----------------------------------------------------------------------------

-- Asset Current Status View
CREATE VIEW IF NOT EXISTS vw_asset_current_status AS
SELECT
    a.asset_id,
    a.asset_name,
    a.asset_type,
    a.criticality,
    a.criticality_score,
    a.downtime_cost_usd_per_hr,
    k.summary_date,
    k.availability_pct,
    k.reliability_score,
    k.mtbf_hrs,
    k.mttr_hrs,
    k.downtime_hrs,
    k.failure_count,
    k.maintenance_compliance_pct,
    k.maintenance_cost_usd,
    k.health_score,
    k.risk_level,
    k.failure_probability_30d,
    k.maintenance_priority_score,
    CASE
        WHEN k.availability_pct >= 97.0 THEN 'Green'
        WHEN k.availability_pct >= 93.0 THEN 'Amber'
        ELSE 'Red'
    END AS availability_rag,
    CASE
        WHEN k.health_score >= 80 THEN 'Green'
        WHEN k.health_score >= 60 THEN 'Amber'
        ELSE 'Red'
    END AS health_rag
FROM assets a
LEFT JOIN kpi_daily_summary k
    ON a.asset_id = k.asset_id
    AND k.summary_date = (
        SELECT MAX(summary_date)
        FROM kpi_daily_summary
        WHERE asset_id = a.asset_id
    )
WHERE a.is_active = 1;

-- Monthly KPI Rollup View
CREATE VIEW IF NOT EXISTS vw_monthly_kpi_rollup AS
SELECT
    asset_id,
    strftime('%Y-%m', summary_date) AS year_month,
    AVG(availability_pct)            AS avg_availability_pct,
    AVG(reliability_score)           AS avg_reliability_score,
    AVG(mtbf_hrs)                    AS avg_mtbf_hrs,
    AVG(mttr_hrs)                    AS avg_mttr_hrs,
    SUM(downtime_hrs)                AS total_downtime_hrs,
    SUM(failure_count)               AS total_failures,
    AVG(maintenance_compliance_pct)  AS avg_maintenance_compliance_pct,
    SUM(maintenance_cost_usd)        AS total_maintenance_cost_usd,
    AVG(health_score)                AS avg_health_score
FROM kpi_daily_summary
GROUP BY asset_id, strftime('%Y-%m', summary_date);

-- Failure Mode Pareto View
CREATE VIEW IF NOT EXISTS vw_failure_pareto AS
SELECT
    failure_category,
    COUNT(*)                          AS failure_count,
    SUM(downtime_hours)               AS total_downtime_hrs,
    SUM(financial_impact_usd)         AS total_financial_impact_usd,
    ROUND(AVG(time_to_repair_hrs), 2) AS avg_ttr_hrs,
    COUNT(*) * 100.0 / SUM(COUNT(*)) OVER () AS pct_of_total
FROM failure_events
GROUP BY failure_category
ORDER BY failure_count DESC;
