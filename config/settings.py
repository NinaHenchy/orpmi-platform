"""
ORPMI Platform Configuration
Central configuration registry for all platform components.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ─────────────────────────────────────────────
# BASE PATHS
# ─────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
EXPORTS_DIR = DATA_DIR / "exports"
DATABASE_DIR = BASE_DIR / "database"
LOGS_DIR = BASE_DIR / "logs"
MODELS_DIR = BASE_DIR / "models"

# ─────────────────────────────────────────────
# DATABASE
# ─────────────────────────────────────────────
DB_TYPE = os.getenv("DB_TYPE", "sqlite")
SQLITE_DB_PATH = BASE_DIR / "database" / "orpmi_dev.db"
POSTGRES_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://orpmi_user:orpmi_pass@localhost:5432/orpmi_db"
)

DATABASE_URL = str(SQLITE_DB_PATH) if DB_TYPE == "sqlite" else POSTGRES_URL

# ─────────────────────────────────────────────
# FACILITY CONFIGURATION
# ─────────────────────────────────────────────
FACILITY_NAME = "Offshore Production Complex — OPC-Alpha"
FACILITY_CODE = "OPC-A"
OPERATING_COMPANY = "ORPMI Energy Operations"
FIELD_NAME = "Alpha Field Development"
PLATFORM_TYPE = "Fixed Production Platform"
FACILITY_CAPACITY_BOPD = 45000   # barrels of oil per day
OIL_PRICE_USD = 82.50            # USD/barrel — basis for downtime cost calculation
GAS_PRICE_USD = 3.20             # USD/MMBTU

# ─────────────────────────────────────────────
# ASSET REGISTRY — SOURCE OF TRUTH
# ─────────────────────────────────────────────
ASSET_REGISTRY = {
    "P-101": {
        "name": "Crude Transfer Pump",
        "type": "Centrifugal Pump",
        "area": "Production",
        "system": "Crude Transfer System",
        "criticality": "Critical",
        "criticality_score": 5,
        "design_pressure_bar": 45.0,
        "design_temp_c": 85.0,
        "rated_flow_m3h": 320.0,
        "manufacturer": "Flowserve",
        "model": "PVWM 14x12-22",
        "commission_year": 2018,
        "replacement_cost_usd": 480000,
        "downtime_cost_usd_per_hr": 18500,
        "pm_interval_days": 90,
        "overhaul_interval_hrs": 8760,
        "target_availability_pct": 97.5,
    },
    "P-202": {
        "name": "Export Pump",
        "type": "Centrifugal Pump",
        "area": "Export",
        "system": "Crude Export System",
        "criticality": "Critical",
        "criticality_score": 5,
        "design_pressure_bar": 72.0,
        "design_temp_c": 70.0,
        "rated_flow_m3h": 450.0,
        "manufacturer": "Sulzer",
        "model": "BB3 HPump 450",
        "commission_year": 2017,
        "replacement_cost_usd": 620000,
        "downtime_cost_usd_per_hr": 24000,
        "pm_interval_days": 90,
        "overhaul_interval_hrs": 8760,
        "target_availability_pct": 98.0,
    },
    "C-201": {
        "name": "Gas Compressor",
        "type": "Reciprocating Compressor",
        "area": "Gas Processing",
        "system": "Gas Compression System",
        "criticality": "Critical",
        "criticality_score": 5,
        "design_pressure_bar": 125.0,
        "design_temp_c": 110.0,
        "rated_flow_m3h": 85000.0,
        "manufacturer": "Dresser-Rand",
        "model": "HHE-VL Reciprocating",
        "commission_year": 2016,
        "replacement_cost_usd": 2100000,
        "downtime_cost_usd_per_hr": 31000,
        "pm_interval_days": 60,
        "overhaul_interval_hrs": 4380,
        "target_availability_pct": 96.0,
    },
    "TK-105": {
        "name": "Crude Storage Tank",
        "type": "Fixed Roof Storage Tank",
        "area": "Storage",
        "system": "Crude Oil Storage System",
        "criticality": "High",
        "criticality_score": 4,
        "design_pressure_bar": 1.05,
        "design_temp_c": 60.0,
        "rated_flow_m3h": None,
        "manufacturer": "CB&I",
        "model": "API 650 Fixed Roof",
        "commission_year": 2015,
        "replacement_cost_usd": 850000,
        "downtime_cost_usd_per_hr": 12000,
        "pm_interval_days": 180,
        "overhaul_interval_hrs": 26280,
        "target_availability_pct": 99.0,
    },
    "HX-401": {
        "name": "Crude/Condensate Heat Exchanger",
        "type": "Shell and Tube Heat Exchanger",
        "area": "Process",
        "system": "Heat Recovery System",
        "criticality": "High",
        "criticality_score": 4,
        "design_pressure_bar": 55.0,
        "design_temp_c": 150.0,
        "rated_flow_m3h": 210.0,
        "manufacturer": "TEMA",
        "model": "BEM-Series 410",
        "commission_year": 2018,
        "replacement_cost_usd": 380000,
        "downtime_cost_usd_per_hr": 9500,
        "pm_interval_days": 120,
        "overhaul_interval_hrs": 8760,
        "target_availability_pct": 97.0,
    },
    "V-301": {
        "name": "Three-Phase Gas Separator",
        "type": "Horizontal Pressure Vessel",
        "area": "Separation",
        "system": "Production Separation System",
        "criticality": "Critical",
        "criticality_score": 5,
        "design_pressure_bar": 95.0,
        "design_temp_c": 95.0,
        "rated_flow_m3h": 520.0,
        "manufacturer": "CECO Environmental",
        "model": "HPS-900 Three-Phase",
        "commission_year": 2016,
        "replacement_cost_usd": 1400000,
        "downtime_cost_usd_per_hr": 28000,
        "pm_interval_days": 90,
        "overhaul_interval_hrs": 8760,
        "target_availability_pct": 97.5,
    },
}

# ─────────────────────────────────────────────
# FAILURE CATEGORIES (ISO 14224 aligned)
# ─────────────────────────────────────────────
FAILURE_CATEGORIES = [
    "Mechanical Failure",
    "Electrical Failure",
    "Instrumentation Failure",
    "Corrosion / Erosion",
    "Seal / Gasket Failure",
    "Vibration Fatigue",
    "Process Upset",
    "Fouling / Blockage",
    "Overtemperature",
    "Overpressure",
    "Operator Error",
    "External Damage",
]

# ─────────────────────────────────────────────
# MAINTENANCE TYPES
# ─────────────────────────────────────────────
MAINTENANCE_TYPES = [
    "Preventive Maintenance",
    "Corrective Maintenance",
    "Condition-Based Maintenance",
    "Predictive Maintenance",
    "Breakdown Maintenance",
    "Overhaul",
    "Inspection",
    "Lubrication",
    "Calibration",
    "Replacement",
]

# ─────────────────────────────────────────────
# KPI THRESHOLDS
# ─────────────────────────────────────────────
KPI_THRESHOLDS = {
    "availability_green": 97.0,
    "availability_amber": 93.0,
    "availability_red": 90.0,
    "mtbf_green_hrs": 720,
    "mtbf_amber_hrs": 360,
    "reliability_score_green": 85,
    "reliability_score_amber": 70,
    "maintenance_compliance_green": 90,
    "maintenance_compliance_amber": 75,
    "health_score_green": 80,
    "health_score_amber": 60,
    "health_score_red": 40,
}

# ─────────────────────────────────────────────
# SIMULATION PARAMETERS
# ─────────────────────────────────────────────
SIMULATION_DAYS = 365
SIMULATION_START_DATE = "2024-01-01"
SIMULATION_END_DATE = "2024-12-31"
RANDOM_SEED = 42
