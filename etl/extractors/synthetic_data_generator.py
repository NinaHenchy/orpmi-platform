"""
ORPMI Synthetic Industrial Data Generator
==========================================
Generates realistic Oil & Gas operational data for 6 production assets
across a full calendar year (2024).

Data characteristics:
- Sensor readings follow physics-based degradation curves
- Failures are correlated with vibration and temperature exceedances
- Maintenance records reflect real PM scheduling patterns
- Downtime costs are anchored to facility production rates
- ISO 14224 failure taxonomy is used throughout
"""

import sys
import random
import math
from pathlib import Path
from datetime import datetime, date, timedelta

import numpy as np
import pandas as pd
from loguru import logger

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config.settings import (
    ASSET_REGISTRY, FAILURE_CATEGORIES, MAINTENANCE_TYPES,
    SIMULATION_DAYS, SIMULATION_START_DATE, RANDOM_SEED,
    FACILITY_CAPACITY_BOPD, OIL_PRICE_USD
)

np.random.seed(RANDOM_SEED)
random.seed(RANDOM_SEED)

START_DATE = datetime.strptime(SIMULATION_START_DATE, "%Y-%m-%d").date()
DATES = [START_DATE + timedelta(days=i) for i in range(SIMULATION_DAYS)]


# ─────────────────────────────────────────────────────────────────────────────
# ASSET BASELINE PARAMETERS
# Physics-based parameter envelopes per asset type
# ─────────────────────────────────────────────────────────────────────────────
ASSET_SENSOR_PROFILES = {
    "P-101": {
        "base_vibration": 1.8,   "vibration_sigma": 0.4,  "vibration_trend": 0.003,
        "base_temp": 68.0,       "temp_sigma": 3.5,        "temp_trend": 0.008,
        "base_pressure": 38.0,   "pressure_sigma": 2.0,
        "base_flow": 295.0,      "flow_sigma": 12.0,
        "base_power": 185.0,     "power_sigma": 8.0,
        "base_efficiency": 88.0, "efficiency_sigma": 2.5,  "efficiency_trend": -0.005,
        "failure_rate_annual": 3.2,
        "pm_compliance_base": 0.88,
    },
    "P-202": {
        "base_vibration": 1.6,   "vibration_sigma": 0.35, "vibration_trend": 0.002,
        "base_temp": 58.0,       "temp_sigma": 3.0,        "temp_trend": 0.005,
        "base_pressure": 65.0,   "pressure_sigma": 3.0,
        "base_flow": 420.0,      "flow_sigma": 15.0,
        "base_power": 245.0,     "power_sigma": 10.0,
        "base_efficiency": 91.0, "efficiency_sigma": 2.0,  "efficiency_trend": -0.003,
        "failure_rate_annual": 2.8,
        "pm_compliance_base": 0.92,
    },
    "C-201": {
        "base_vibration": 3.2,   "vibration_sigma": 0.7,  "vibration_trend": 0.008,
        "base_temp": 95.0,       "temp_sigma": 5.0,        "temp_trend": 0.015,
        "base_pressure": 108.0,  "pressure_sigma": 5.0,
        "base_flow": 78000.0,    "flow_sigma": 2500.0,
        "base_power": 1850.0,    "power_sigma": 60.0,
        "base_efficiency": 82.0, "efficiency_sigma": 3.0,  "efficiency_trend": -0.010,
        "failure_rate_annual": 5.5,
        "pm_compliance_base": 0.78,
    },
    "TK-105": {
        "base_vibration": 0.3,   "vibration_sigma": 0.05, "vibration_trend": 0.0001,
        "base_temp": 48.0,       "temp_sigma": 2.0,        "temp_trend": 0.001,
        "base_pressure": 1.02,   "pressure_sigma": 0.03,
        "base_flow": None,       "flow_sigma": None,
        "base_power": 18.0,      "power_sigma": 2.0,
        "base_efficiency": 98.0, "efficiency_sigma": 0.5,  "efficiency_trend": -0.001,
        "failure_rate_annual": 0.8,
        "pm_compliance_base": 0.95,
    },
    "HX-401": {
        "base_vibration": 0.8,   "vibration_sigma": 0.15, "vibration_trend": 0.002,
        "base_temp": 128.0,      "temp_sigma": 6.0,        "temp_trend": 0.010,
        "base_pressure": 48.0,   "pressure_sigma": 2.5,
        "base_flow": 195.0,      "flow_sigma": 10.0,
        "base_power": 42.0,      "power_sigma": 4.0,
        "base_efficiency": 85.0, "efficiency_sigma": 3.5,  "efficiency_trend": -0.015,
        "failure_rate_annual": 2.1,
        "pm_compliance_base": 0.85,
    },
    "V-301": {
        "base_vibration": 1.2,   "vibration_sigma": 0.25, "vibration_trend": 0.004,
        "base_temp": 82.0,       "temp_sigma": 4.0,        "temp_trend": 0.008,
        "base_pressure": 85.0,   "pressure_sigma": 4.0,
        "base_flow": 495.0,      "flow_sigma": 18.0,
        "base_power": 125.0,     "power_sigma": 8.0,
        "base_efficiency": 87.0, "efficiency_sigma": 2.8,  "efficiency_trend": -0.007,
        "failure_rate_annual": 4.0,
        "pm_compliance_base": 0.82,
    },
}

DETECTION_METHODS = [
    "Condition Monitoring Round", "Operator Report", "DCS Alarm",
    "Vibration Survey", "Thermographic Inspection", "Routine Inspection",
    "Process Deviation Alert", "SCADA Alert"
]

TECHNICIANS = [
    "Ibrahim Yusuf", "Chukwuemeka Eze", "Oluwaseun Adeyemi",
    "Fatima Al-Rashid", "Emeka Okafor", "Amara Diallo",
    "Taiwo Ogundimu", "Mohammed Al-Farsi", "Ngozi Okonkwo",
    "Babatunde Fashola"
]

INSPECTORS = [
    "David Osei", "Grace Mensah", "Kofi Asante",
    "Aisha Bello", "Chidi Nwosu", "Sola Adewale"
]


def _degradation_factor(day_index: int, total_days: int) -> float:
    """Simulates gradual asset degradation over the year (0→1 scale)."""
    return (day_index / total_days) ** 1.2


def _add_seasonal_variation(value: float, day_of_year: int, amplitude_pct: float = 0.03) -> float:
    """Adds seasonal temperature/pressure variation (common in offshore environments)."""
    seasonal = amplitude_pct * math.sin(2 * math.pi * day_of_year / 365)
    return value * (1 + seasonal)


def generate_assets_table() -> pd.DataFrame:
    """Generate the master asset registry DataFrame."""
    records = []
    for asset_id, info in ASSET_REGISTRY.items():
        records.append({
            "asset_id": asset_id,
            "asset_name": info["name"],
            "asset_type": info["type"],
            "area": info["area"],
            "system_name": info["system"],
            "criticality": info["criticality"],
            "criticality_score": info["criticality_score"],
            "manufacturer": info["manufacturer"],
            "model_number": info["model"],
            "commission_year": info["commission_year"],
            "design_pressure_bar": info["design_pressure_bar"],
            "design_temp_c": info["design_temp_c"],
            "rated_flow_m3h": info.get("rated_flow_m3h"),
            "replacement_cost_usd": info["replacement_cost_usd"],
            "downtime_cost_usd_per_hr": info["downtime_cost_usd_per_hr"],
            "pm_interval_days": info["pm_interval_days"],
            "overhaul_interval_hrs": info["overhaul_interval_hrs"],
            "target_availability_pct": info["target_availability_pct"],
            "is_active": 1,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        })
    df = pd.DataFrame(records)
    logger.info(f"Assets table generated: {len(df)} assets")
    return df


def generate_failure_events(asset_id: str) -> pd.DataFrame:
    """
    Generate failure events for one asset for the full year.
    Failure probability is elevated after sensor threshold breaches
    and when vibration/temperature exceed design limits.
    """
    profile = ASSET_SENSOR_PROFILES[asset_id]
    asset_info = ASSET_REGISTRY[asset_id]
    annual_rate = profile["failure_rate_annual"]
    downtime_cost = asset_info["downtime_cost_usd_per_hr"]

    records = []
    failure_id = 1
    last_failure_date = None

    # Assign failures randomly across the year weighted toward degraded periods
    weights = np.array([
        0.5 + _degradation_factor(i, SIMULATION_DAYS) for i in range(SIMULATION_DAYS)
    ])
    weights /= weights.sum()

    expected_failures = int(np.round(annual_rate * np.random.uniform(0.8, 1.2)))
    failure_day_indices = np.random.choice(
        range(SIMULATION_DAYS), size=expected_failures, replace=False, p=weights
    )
    failure_day_indices = sorted(failure_day_indices)

    for idx in failure_day_indices:
        failure_date = DATES[idx]

        # Enforce minimum gap between failures (MTBF > 0)
        if last_failure_date and (failure_date - last_failure_date).days < 14:
            continue

        severity_roll = random.random()
        if severity_roll > 0.85:
            severity = "Critical"
            downtime = round(random.uniform(24, 96), 1)
        elif severity_roll > 0.55:
            severity = "Major"
            downtime = round(random.uniform(8, 32), 1)
        elif severity_roll > 0.20:
            severity = "Minor"
            downtime = round(random.uniform(2, 10), 1)
        else:
            severity = "Negligible"
            downtime = round(random.uniform(0.5, 3), 1)

        category = random.choices(
            FAILURE_CATEGORIES,
            weights=[20, 12, 10, 18, 14, 11, 5, 6, 2, 1, 0, 1],
            k=1
        )[0]

        ttr = round(downtime * random.uniform(0.7, 0.95), 1)
        ttd = round(random.uniform(0.5, 4.0), 1)

        production_loss = round(
            (downtime / 24) * FACILITY_CAPACITY_BOPD * 0.15 * random.uniform(0.6, 1.0),
            1
        )
        financial_impact = round(downtime * downtime_cost * random.uniform(0.85, 1.1), 0)

        records.append({
            "asset_id": asset_id,
            "failure_date": failure_date.isoformat(),
            "failure_time": f"{random.randint(0,23):02d}:{random.randint(0,59):02d}:00",
            "failure_category": category,
            "failure_description": _failure_description(asset_id, category, severity),
            "failure_severity": severity,
            "detection_method": random.choice(DETECTION_METHODS),
            "downtime_hours": downtime,
            "time_to_repair_hrs": ttr,
            "time_to_detect_hrs": ttd,
            "production_loss_bbls": production_loss,
            "financial_impact_usd": financial_impact,
            "root_cause": _root_cause(category),
            "corrective_action": _corrective_action(category),
            "is_recurrence": int(random.random() < 0.18),
            "work_order_id": f"WO-{asset_id}-{failure_date.strftime('%Y%m%d')}-{failure_id:03d}",
            "reported_by": random.choice(TECHNICIANS),
            "closed_date": (failure_date + timedelta(hours=ttr + ttd)).isoformat(),
        })

        last_failure_date = failure_date
        failure_id += 1

    df = pd.DataFrame(records) if records else pd.DataFrame()
    logger.debug(f"  Failures generated for {asset_id}: {len(df)}")
    return df


def _failure_description(asset_id: str, category: str, severity: str) -> str:
    asset_name = ASSET_REGISTRY[asset_id]["name"]
    descriptions = {
        "Mechanical Failure":       f"{asset_name} — {severity} mechanical failure. Abnormal noise and vibration detected. Equipment isolated for inspection.",
        "Electrical Failure":       f"{asset_name} — {severity} electrical fault on motor control circuit. MCC tripped on overload. Electrical team mobilised.",
        "Instrumentation Failure":  f"{asset_name} — {severity} instrumentation failure. Pressure transmitter reading erratic. Equipment placed on manual monitoring.",
        "Corrosion / Erosion":      f"{asset_name} — {severity} corrosion/erosion finding during inspection. Wall thinning detected at inlet nozzle. Fitness-for-service assessment initiated.",
        "Seal / Gasket Failure":    f"{asset_name} — {severity} seal failure. Fluid leakage observed at mechanical seal assembly. Equipment shutdown, containment deployed.",
        "Vibration Fatigue":        f"{asset_name} — {severity} vibration exceedance. ISO 10816 Class IV threshold exceeded. Balancing and alignment check required.",
        "Process Upset":            f"{asset_name} — {severity} process upset. Operating parameters deviated beyond allowable envelope. Equipment tripped on safety interlock.",
        "Fouling / Blockage":       f"{asset_name} — {severity} fouling/blockage. Flow restriction detected. High differential pressure confirmed. Chemical treatment initiated.",
        "Overtemperature":          f"{asset_name} — {severity} overtemperature event. Bearing temperature exceeded alarm setpoint. Cooling system investigated.",
        "Overpressure":             f"{asset_name} — {severity} overpressure transient. Safety relief valve actuated. Process stabilised. RV condition assessed.",
        "Operator Error":           f"{asset_name} — {severity} incident attributed to operational deviation. Incorrect valve positioning during commissioning. No physical damage confirmed.",
        "External Damage":          f"{asset_name} — {severity} external impact. Physical damage observed during walkthrough. Structural integrity assessment required.",
    }
    return descriptions.get(category, f"{asset_name} failure event — {category}.")


def _root_cause(category: str) -> str:
    rca = {
        "Mechanical Failure":       "Bearing wear beyond replacement threshold due to overextended PM interval. RCFA confirmed inadequate lubrication schedule.",
        "Electrical Failure":       "Insulation degradation on motor winding. Moisture ingress through cable gland seal. Accelerated by ambient humidity cycling.",
        "Instrumentation Failure":  "Drift in pressure transmitter signal due to process fluid contamination in impulse line. Requires periodic purging.",
        "Corrosion / Erosion":      "Accelerated pitting corrosion in high-velocity zone. Inhibitor injection rate insufficient at elevated throughput.",
        "Seal / Gasket Failure":    "Mechanical seal face wear. Operating beyond duty point — process flow exceeding design conditions during peak demand.",
        "Vibration Fatigue":        "Misalignment induced after maintenance intervention. Coupling realignment tolerance not verified post-reinstallation.",
        "Process Upset":            "Upstream slug flow from production separator causing transient pressure spikes beyond operating envelope.",
        "Fouling / Blockage":       "Wax deposition from high pour-point crude. Insufficient heat tracing at low-flow conditions during startup.",
        "Overtemperature":          "Cooling water flow reduction. Strainer blockage on cooling water supply header. Preventive cleaning interval overdue.",
        "Overpressure":             "Control valve fail-open on power loss. Relief valve sized for single relief scenario — additional event exceeded capacity.",
        "Operator Error":           "Procedure not followed. Bypass valve left open during handover. Permit-to-work deviation noted.",
        "External Damage":          "Third-party contractor impact during adjacent scaffolding erection. Pre-work survey not completed.",
    }
    return rca.get(category, "Root cause under investigation.")


def _corrective_action(category: str) -> str:
    ca = {
        "Mechanical Failure":       "Bearing replacement completed. Lubrication frequency increased. Vibration monitoring frequency elevated. PM interval revised to 60 days.",
        "Electrical Failure":       "Motor rewound and tested. Cable glands resealed with IP68-rated fittings. Megger test passed. Insulation monitoring device installed.",
        "Instrumentation Failure":  "Transmitter replaced with upgraded model. Impulse line purge procedure added to PM scope. Secondary transmitter installed.",
        "Corrosion / Erosion":      "Affected section weld-repaired and hydrotest completed. Inhibitor injection rate increased by 30%. Next inspection at 6 months.",
        "Seal / Gasket Failure":    "Mechanical seal replaced with upgraded material grade. Operating point adjusted. Duty/standby changeover frequency increased.",
        "Vibration Fatigue":        "Coupling realigned to OEM tolerance (±0.025mm). Soft foot corrected. Baseline vibration survey completed and recorded.",
        "Process Upset":            "Slug catcher installed upstream. Control logic review completed. Trip setpoints revised. Operator training refreshed.",
        "Fouling / Blockage":       "Chemical cleaning completed. Pigging program introduced. Pour point depressant added to chemical injection schedule.",
        "Overtemperature":          "Cooling water strainer cleaned. Differential pressure indicator installed. Strainer cleaning added to daily operator rounds.",
        "Overpressure":             "Control valve positioner calibrated. Fail-safe logic reviewed. Additional relief capacity provision under review.",
        "Operator Error":           "Toolbox talk conducted. Procedure revised with pictorial steps. Permit-to-work refresher training completed for all operators.",
        "External Damage":          "Damage repaired and NDE completed. Third-party work exclusion zone formalised. Pre-work survey made mandatory.",
    }
    return ca.get(category, "Corrective action completed. Return to service approved.")


def generate_operating_data(asset_id: str, failure_events: pd.DataFrame) -> pd.DataFrame:
    """
    Generate daily operating data with physics-based sensor readings.
    Sensor values degrade toward failure events and recover after maintenance.
    """
    profile = ASSET_SENSOR_PROFILES[asset_id]
    asset_info = ASSET_REGISTRY[asset_id]

    # Build set of failure dates for this asset
    if not failure_events.empty:
        failed_dates = set(failure_events["failure_date"].tolist())
        downtime_map = dict(zip(failure_events["failure_date"], failure_events["downtime_hours"]))
    else:
        failed_dates = set()
        downtime_map = {}

    cumulative_hours = float(asset_info["commission_year"] and
                              (2024 - asset_info["commission_year"]) * 8400 or 12000)

    records = []
    ytd_runtime = 0.0
    ytd_downtime = 0.0
    recent_failure_day = -999

    for i, dt in enumerate(DATES):
        dt_str = dt.isoformat()
        day_of_year = dt.timetuple().tm_yday
        deg = _degradation_factor(i, SIMULATION_DAYS)
        proximity_to_failure = _failure_proximity_factor(i, failure_events, DATES)

        is_failed_day = dt_str in failed_dates
        is_post_failure = (i - recent_failure_day) <= 3

        if is_failed_day:
            recent_failure_day = i
            downtime = min(downtime_map.get(dt_str, random.uniform(4, 24)), 24.0)
            operating_hrs = max(24.0 - downtime, 0)
            is_running = int(operating_hrs > 0)
        else:
            downtime = 0.0
            operating_hrs = 24.0 if not is_post_failure else random.uniform(18, 24)
            is_running = 1

        ytd_runtime += operating_hrs
        ytd_downtime += downtime
        cumulative_hours += operating_hrs

        # Vibration — increases with degradation and proximity to failure
        vib_base = profile["base_vibration"] + (deg * 2.5 * profile["vibration_trend"] * 100)
        vib_spike = proximity_to_failure * 3.0
        if is_post_failure:
            vib_spike *= 0.3
        vibration = max(0.1, np.random.normal(vib_base + vib_spike, profile["vibration_sigma"]))
        vibration = round(_add_seasonal_variation(vibration, day_of_year, 0.05), 3)

        # Temperature
        temp_drift = deg * profile["temp_trend"] * SIMULATION_DAYS * 0.5
        temp = np.random.normal(profile["base_temp"] + temp_drift, profile["temp_sigma"])
        temp = round(_add_seasonal_variation(temp, day_of_year, 0.04), 2)

        # Pressure
        pressure = round(np.random.normal(profile["base_pressure"], profile["pressure_sigma"]), 2)

        # Flow
        if profile["base_flow"] is not None:
            flow = round(max(0, np.random.normal(
                profile["base_flow"] * (1 - deg * 0.05),
                profile["flow_sigma"]
            )), 1) if is_running else 0.0
        else:
            flow = None

        # Power and efficiency
        power = round(max(0, np.random.normal(
            profile["base_power"] * (1 + deg * 0.06),
            profile["power_sigma"]
        )), 1) if is_running else 0.0

        efficiency = round(max(30, np.random.normal(
            profile["base_efficiency"] + profile["efficiency_trend"] * i * 0.8,
            profile["efficiency_sigma"]
        )), 2) if is_running else 0.0

        records.append({
            "asset_id": asset_id,
            "record_date": dt_str,
            "operating_hours_daily": round(operating_hrs, 2),
            "operating_hours_cumulative": round(cumulative_hours, 1),
            "runtime_hours_ytd": round(ytd_runtime, 1),
            "downtime_hours_daily": round(downtime, 2),
            "downtime_hours_ytd": round(ytd_downtime, 1),
            "operating_temp_c": round(temp, 2) if is_running else None,
            "operating_pressure_bar": round(pressure, 2) if is_running else None,
            "vibration_mm_s": round(vibration, 3) if is_running else None,
            "flow_rate_m3h": flow,
            "power_consumption_kw": power,
            "efficiency_pct": efficiency,
            "is_running": is_running,
        })

    df = pd.DataFrame(records)
    logger.debug(f"  Operating data generated for {asset_id}: {len(df)} daily records")
    return df


def _failure_proximity_factor(day_idx: int, failure_events: pd.DataFrame, dates: list) -> float:
    """Returns 0–1 factor representing proximity to next failure (for sensor spike modelling)."""
    if failure_events.empty:
        return 0.0
    current_date = dates[day_idx].isoformat()
    future_failures = failure_events[failure_events["failure_date"] > current_date]
    if future_failures.empty:
        return 0.0
    next_failure_date = future_failures["failure_date"].min()
    days_to_failure = (datetime.strptime(next_failure_date, "%Y-%m-%d").date()
                       - dates[day_idx]).days
    if days_to_failure <= 0:
        return 1.0
    if days_to_failure > 30:
        return 0.0
    return max(0.0, (30 - days_to_failure) / 30.0)


def generate_maintenance_records(asset_id: str) -> pd.DataFrame:
    """
    Generate preventive and corrective maintenance records.
    PM intervals are asset-specific. Compliance is randomised within
    realistic bands (70–95%) depending on asset priority.
    """
    asset_info = ASSET_REGISTRY[asset_id]
    profile = ASSET_SENSOR_PROFILES[asset_id]
    pm_interval = asset_info["pm_interval_days"]
    compliance_base = profile["pm_compliance_base"]

    records = []
    wo_counter = 1

    # Preventive Maintenance schedule
    pm_date = START_DATE + timedelta(days=random.randint(0, pm_interval // 3))
    while pm_date <= DATES[-1]:
        is_compliant = random.random() < compliance_base
        overdue_days = 0 if is_compliant else random.randint(3, 21)
        actual_date = pm_date + timedelta(days=overdue_days)
        if actual_date > DATES[-1]:
            break

        duration = round(random.uniform(3.0, 12.0), 1)
        estimated = round(random.uniform(2000, 15000), 0)
        actual = round(estimated * random.uniform(0.85, 1.35), 0)

        records.append({
            "asset_id": asset_id,
            "work_order_id": f"PM-{asset_id}-{actual_date.strftime('%Y%m%d')}-{wo_counter:03d}",
            "maintenance_type": "Preventive Maintenance",
            "maintenance_date": actual_date.isoformat(),
            "scheduled_date": pm_date.isoformat(),
            "completion_date": (actual_date + timedelta(hours=duration)).isoformat(),
            "maintenance_description": _pm_description(asset_id),
            "technician": random.choice(TECHNICIANS),
            "duration_hrs": duration,
            "parts_replaced": _parts_replaced(asset_id),
            "estimated_cost_usd": estimated,
            "actual_cost_usd": actual,
            "compliance_flag": int(is_compliant),
            "overdue_days": overdue_days,
            "next_due_date": (actual_date + timedelta(days=pm_interval)).isoformat(),
            "failure_prevented": int(random.random() < 0.25),
            "inspection_score": round(random.uniform(72, 96), 1),
            "notes": "Routine PM executed per maintenance schedule. Work order closed.",
        })
        pm_date += timedelta(days=pm_interval)
        wo_counter += 1

    # Overhaul (if asset overhaul interval fits within year)
    asset_age_hrs = (2024 - asset_info["commission_year"]) * 8400
    if asset_age_hrs > 0 and asset_age_hrs % asset_info["overhaul_interval_hrs"] < 8760:
        oh_date = START_DATE + timedelta(days=random.randint(30, 300))
        if oh_date <= DATES[-1]:
            records.append({
                "asset_id": asset_id,
                "work_order_id": f"OH-{asset_id}-{oh_date.strftime('%Y%m%d')}-001",
                "maintenance_type": "Overhaul",
                "maintenance_date": oh_date.isoformat(),
                "scheduled_date": oh_date.isoformat(),
                "completion_date": (oh_date + timedelta(days=5)).isoformat(),
                "maintenance_description": _overhaul_description(asset_id),
                "technician": random.choice(TECHNICIANS),
                "duration_hrs": round(random.uniform(48, 120), 1),
                "parts_replaced": _overhaul_parts(asset_id),
                "estimated_cost_usd": round(random.uniform(45000, 220000), 0),
                "actual_cost_usd": round(random.uniform(42000, 230000), 0),
                "compliance_flag": 1,
                "overdue_days": 0,
                "next_due_date": (oh_date + timedelta(days=365)).isoformat(),
                "failure_prevented": 1,
                "inspection_score": round(random.uniform(88, 98), 1),
                "notes": "Major overhaul completed. All components inspected, worn parts replaced. Performance test passed.",
            })
            wo_counter += 1

    # Corrective maintenance (tied to failures) — added later by ETL post-join
    # Condition-based maintenance (random 1–3 per asset)
    cbl_count = random.randint(1, 3)
    for _ in range(cbl_count):
        cbl_date = START_DATE + timedelta(days=random.randint(0, 364))
        records.append({
            "asset_id": asset_id,
            "work_order_id": f"CBM-{asset_id}-{cbl_date.strftime('%Y%m%d')}-{wo_counter:03d}",
            "maintenance_type": "Condition-Based Maintenance",
            "maintenance_date": cbl_date.isoformat(),
            "scheduled_date": None,
            "completion_date": (cbl_date + timedelta(days=1)).isoformat(),
            "maintenance_description": f"Condition-based intervention triggered by elevated vibration/temperature readings on {ASSET_REGISTRY[asset_id]['name']}.",
            "technician": random.choice(TECHNICIANS),
            "duration_hrs": round(random.uniform(4.0, 18.0), 1),
            "parts_replaced": _parts_replaced(asset_id),
            "estimated_cost_usd": round(random.uniform(3000, 25000), 0),
            "actual_cost_usd": round(random.uniform(2800, 26000), 0),
            "compliance_flag": 1,
            "overdue_days": 0,
            "next_due_date": None,
            "failure_prevented": int(random.random() < 0.55),
            "inspection_score": round(random.uniform(65, 90), 1),
            "notes": "CBM intervention completed following condition monitoring alert. Asset returned to normal operating envelope.",
        })
        wo_counter += 1

    df = pd.DataFrame(records)
    logger.debug(f"  Maintenance records generated for {asset_id}: {len(df)}")
    return df


def _pm_description(asset_id: str) -> str:
    asset_type = ASSET_REGISTRY[asset_id]["type"]
    descs = {
        "Centrifugal Pump": "Routine PM: Check alignment, inspect mechanical seal, lubricate bearings, test vibration baseline, inspect impeller condition, verify instrument calibration.",
        "Reciprocating Compressor": "Routine PM: Inspect valves, replace piston rings, check cylinder liners, lubricate crossheads, test vibration and temperature, verify safety systems.",
        "Fixed Roof Storage Tank": "Routine PM: Inspect shell for corrosion, check roof drain, test level instruments, inspect vents and pressure relief, check cathodic protection readings.",
        "Shell and Tube Heat Exchanger": "Routine PM: Chemical clean tube bundle, inspect shell/tube for corrosion, test pressure integrity, check baffles and tie-rods, verify instrumentation.",
        "Horizontal Pressure Vessel": "Routine PM: Inspect internal demisters and internals, check nozzle conditions, test safety relief valves, verify level instrument calibration, check corrosion.",
    }
    return descs.get(asset_type, f"Routine preventive maintenance completed per OEM schedule.")


def _overhaul_description(asset_id: str) -> str:
    return (f"Major overhaul of {ASSET_REGISTRY[asset_id]['name']}. Full disassembly and inspection. "
            f"All wear components replaced per OEM schedule. NDT inspection completed. Performance test verified against design envelope.")


def _parts_replaced(asset_id: str) -> str:
    asset_type = ASSET_REGISTRY[asset_id]["type"]
    parts = {
        "Centrifugal Pump": "Mechanical seal set, bearing cartridge, coupling insert, gasket kit",
        "Reciprocating Compressor": "Suction/discharge valves, piston rings, oil filter elements, coupling bolts",
        "Fixed Roof Storage Tank": "Vent gaskets, level gauge glass, drain valve seat, corrosion inhibitor injection fittings",
        "Shell and Tube Heat Exchanger": "Tube bundle gaskets, vent/drain plugs, instrument nozzle fittings",
        "Horizontal Pressure Vessel": "Demister pad section, drain valve, level transmitter impulse tubing, gasket kit",
    }
    return parts.get(asset_type, "Standard PM consumables and gasket kit")


def _overhaul_parts(asset_id: str) -> str:
    asset_type = ASSET_REGISTRY[asset_id]["type"]
    parts = {
        "Centrifugal Pump": "Complete seal kit, both bearings, impeller, wear rings, shaft sleeve, coupling, all gaskets",
        "Reciprocating Compressor": "Full valve overhaul kit, piston rings set, cylinder liner, crosshead pin, all seals, lube oil system service",
        "Fixed Roof Storage Tank": "Full shell NDE inspection, floor plate repairs, new vents, cathodic protection anode replacement, coating",
        "Shell and Tube Heat Exchanger": "Full tube bundle replacement, new shell gaskets, baffle set, new tie-rods, all instrument nozzles",
        "Horizontal Pressure Vessel": "Full internal inspection and recoating, new demister, all nozzle gaskets, instrument replacement set",
    }
    return parts.get(asset_type, "Full overhaul kit per OEM BOM")


def generate_inspection_records(asset_id: str) -> pd.DataFrame:
    """Generate structured inspection records throughout the year."""
    asset_info = ASSET_REGISTRY[asset_id]
    pm_interval = asset_info["pm_interval_days"]

    records = []
    insp_date = START_DATE + timedelta(days=random.randint(5, 30))
    insp_counter = 1

    while insp_date <= DATES[-1]:
        day_index = (insp_date - START_DATE).days
        deg = _degradation_factor(day_index, SIMULATION_DAYS)

        base_score = 88.0 - (deg * 20.0) + random.uniform(-5, 5)
        base_score = max(40.0, min(99.0, base_score))

        if base_score >= 85:
            condition = "Excellent" if base_score >= 95 else "Good"
        elif base_score >= 70:
            condition = "Fair"
        elif base_score >= 55:
            condition = "Poor"
        else:
            condition = "Critical"

        findings = int(max(0, np.random.poisson(max(0.5, deg * 4))))
        critical_findings = int(max(0, findings // 4))

        records.append({
            "asset_id": asset_id,
            "inspection_date": insp_date.isoformat(),
            "inspection_type": random.choice([
                "Routine Inspection", "NDT Survey", "Vibration Survey",
                "Thermographic Survey", "Corrosion Survey"
            ]),
            "inspector_name": random.choice(INSPECTORS),
            "inspection_score": round(base_score, 1),
            "overall_condition": condition,
            "findings_count": findings,
            "critical_findings": critical_findings,
            "corrosion_rate_mm_yr": round(random.uniform(0.05, 0.45) * (1 + deg), 3),
            "wall_thickness_mm": round(random.uniform(8.5, 15.0) * (1 - deg * 0.08), 2),
            "next_inspection_date": (insp_date + timedelta(days=pm_interval)).isoformat(),
            "action_required": int(critical_findings > 0 or base_score < 65),
            "action_description": "Corrective action raised per findings. Work order generated." if critical_findings > 0 else None,
            "report_reference": f"INSP-{asset_id}-{insp_date.strftime('%Y%m')}-{insp_counter:03d}",
        })

        insp_date += timedelta(days=pm_interval)
        insp_counter += 1

    df = pd.DataFrame(records)
    logger.debug(f"  Inspection records generated for {asset_id}: {len(df)}")
    return df


def generate_downtime_log(failure_events: pd.DataFrame) -> pd.DataFrame:
    """Generate granular downtime log from failure events."""
    records = []
    if failure_events.empty:
        return pd.DataFrame()

    downtime_categories = [
        "Equipment Failure", "PM Shutdown", "Awaiting Parts",
        "Process Upset", "Inspection Shutdown", "External Cause"
    ]

    for _, row in failure_events.iterrows():
        start_dt = datetime.fromisoformat(f"{row['failure_date']}T{row['failure_time']}")
        end_dt = start_dt + timedelta(hours=float(row["downtime_hours"]))
        asset_info = ASSET_REGISTRY[row["asset_id"]]
        downtime_cost = asset_info["downtime_cost_usd_per_hr"]

        prod_loss = (float(row["downtime_hours"]) / 24) * FACILITY_CAPACITY_BOPD * 0.12
        fin_impact = float(row["downtime_hours"]) * downtime_cost

        records.append({
            "asset_id": row["asset_id"],
            "downtime_start": start_dt.isoformat(),
            "downtime_end": end_dt.isoformat(),
            "downtime_hours": row["downtime_hours"],
            "downtime_category": "Equipment Failure",
            "downtime_cause": row["failure_description"],
            "production_impact": "Full Loss" if row["failure_severity"] == "Critical"
                                else "Partial" if row["failure_severity"] == "Major"
                                else "Derated" if row["failure_severity"] == "Minor"
                                else "No Impact",
            "production_loss_bbls": round(prod_loss, 1),
            "financial_impact_usd": round(fin_impact, 0),
            "linked_failure_id": None,
            "linked_wo_id": row["work_order_id"],
            "operator_on_duty": random.choice(TECHNICIANS),
        })

    df = pd.DataFrame(records)
    logger.debug(f"  Downtime log generated: {len(df)} entries")
    return df


def compute_kpi_daily_summary(
    asset_id: str,
    operating_data: pd.DataFrame,
    failure_events: pd.DataFrame,
    maintenance_records: pd.DataFrame,
    inspection_records: pd.DataFrame,
) -> pd.DataFrame:
    """
    Compute daily KPI summary per asset.
    This is the pre-aggregation layer consumed by all dashboard visualisations.
    """
    records = []
    asset_info = ASSET_REGISTRY[asset_id]
    target_avail = asset_info["target_availability_pct"]
    downtime_cost = asset_info["downtime_cost_usd_per_hr"]
    pm_interval = asset_info["pm_interval_days"]

    for i, dt in enumerate(DATES):
        dt_str = dt.isoformat()
        # 90-day rolling window
        window_start = max(0, i - 89)
        window_dates = [d.isoformat() for d in DATES[window_start:i + 1]]

        # Operating data for this day
        today_ops = operating_data[operating_data["record_date"] == dt_str]
        if today_ops.empty:
            continue
        row = today_ops.iloc[0]

        # Availability (rolling 90d)
        window_ops = operating_data[operating_data["record_date"].isin(window_dates)]
        total_possible = len(window_dates) * 24
        total_runtime = window_ops["operating_hours_daily"].sum()
        availability = round((total_runtime / total_possible) * 100, 2) if total_possible > 0 else 0

        # Failures in window
        window_failures = failure_events[
            failure_events["failure_date"].isin(window_dates)
        ] if not failure_events.empty else pd.DataFrame()
        failure_count = len(window_failures)

        # MTBF
        total_downtime_window = window_failures["downtime_hours"].sum() if not window_failures.empty else 0
        mtbf = round((total_runtime - total_downtime_window) / max(failure_count, 1), 1)

        # MTTR
        mttr = round(window_failures["time_to_repair_hrs"].mean(), 1) if not window_failures.empty else 0.0

        # Downtime this day
        downtime_today = float(row["downtime_hours_daily"])

        # Maintenance compliance (rolling 90d)
        window_maint = maintenance_records[
            maintenance_records["maintenance_date"].isin(window_dates)
        ] if not maintenance_records.empty else pd.DataFrame()
        if not window_maint.empty:
            compliance_pct = round(window_maint["compliance_flag"].mean() * 100, 1)
            maint_cost = round(window_maint["actual_cost_usd"].sum(), 0)
        else:
            compliance_pct = round(target_avail - 2 + random.uniform(-3, 3), 1)
            maint_cost = 0.0

        # Latest inspection score
        past_inspections = inspection_records[
            inspection_records["inspection_date"] <= dt_str
        ] if not inspection_records.empty else pd.DataFrame()
        inspection_score = past_inspections["inspection_score"].iloc[-1] if not past_inspections.empty else 80.0

        # Health score: weighted composite
        avail_component = min(availability / target_avail * 40, 40)
        insp_component = inspection_score * 0.30
        mtbf_target = 168  # 1 week
        mtbf_component = min(mtbf / mtbf_target * 20, 20)
        compliance_component = compliance_pct * 0.10
        health_score = round(avail_component + insp_component + mtbf_component + compliance_component, 1)
        health_score = max(10.0, min(100.0, health_score))

        # Reliability score: similar composite, different weighting
        reliability_score = round(
            availability * 0.45 + inspection_score * 0.25 + compliance_pct * 0.20 + min(mtbf / 200 * 10, 10),
            1
        )
        reliability_score = max(10.0, min(100.0, reliability_score))

        # Failure probability (heuristic — ML will refine this in Phase 3)
        deg = _degradation_factor(i, SIMULATION_DAYS)
        vibration_today = float(row.get("vibration_mm_s", 0) or 0)
        vib_factor = min(vibration_today / 7.1, 1.0)
        failure_prob = round(min(0.95, deg * 0.4 + vib_factor * 0.3 + (1 - availability / 100) * 0.3), 3)

        # Maintenance priority score
        priority_score = round(
            asset_info["criticality_score"] * 15 +
            (100 - health_score) * 0.5 +
            failure_prob * 20 +
            downtime_cost / 1000 * 0.2,
            1
        )

        # Risk level
        if failure_prob >= 0.65 or health_score < 50:
            risk_level = "Critical"
        elif failure_prob >= 0.40 or health_score < 65:
            risk_level = "High"
        elif failure_prob >= 0.20 or health_score < 78:
            risk_level = "Medium"
        else:
            risk_level = "Low"

        records.append({
            "asset_id": asset_id,
            "summary_date": dt_str,
            "availability_pct": availability,
            "reliability_score": reliability_score,
            "mtbf_hrs": mtbf,
            "mttr_hrs": mttr if mttr > 0 else round(random.uniform(4, 12), 1),
            "downtime_hrs": downtime_today,
            "failure_count": failure_count,
            "maintenance_compliance_pct": compliance_pct,
            "maintenance_cost_usd": maint_cost,
            "health_score": health_score,
            "risk_level": risk_level,
            "failure_probability_30d": failure_prob,
            "maintenance_priority_score": priority_score,
        })

    df = pd.DataFrame(records)
    logger.debug(f"  KPI summary generated for {asset_id}: {len(df)} daily records")
    return df


def run_full_generation() -> dict:
    """
    Master generation function. Returns all DataFrames ready for DB load.
    """
    logger.info("=" * 60)
    logger.info("ORPMI Synthetic Data Generation — START")
    logger.info(f"Facility: Offshore Production Complex OPC-Alpha")
    logger.info(f"Assets: {list(ASSET_REGISTRY.keys())}")
    logger.info(f"Period: {SIMULATION_START_DATE} — 365 days")
    logger.info("=" * 60)

    all_assets = generate_assets_table()

    all_failures, all_operating, all_maintenance = [], [], []
    all_inspections, all_downtime, all_kpis = [], [], []

    for asset_id in ASSET_REGISTRY.keys():
        logger.info(f"Generating data for {asset_id} — {ASSET_REGISTRY[asset_id]['name']}")

        failures = generate_failure_events(asset_id)
        operating = generate_operating_data(asset_id, failures)
        maintenance = generate_maintenance_records(asset_id)
        inspections = generate_inspection_records(asset_id)
        downtime = generate_downtime_log(failures)
        kpis = compute_kpi_daily_summary(asset_id, operating, failures, maintenance, inspections)

        if not failures.empty:
            all_failures.append(failures)
        all_operating.append(operating)
        all_maintenance.append(maintenance)
        all_inspections.append(inspections)
        if not downtime.empty:
            all_downtime.append(downtime)
        all_kpis.append(kpis)

    result = {
        "assets": all_assets,
        "failure_events": pd.concat(all_failures, ignore_index=True) if all_failures else pd.DataFrame(),
        "asset_operating_data": pd.concat(all_operating, ignore_index=True),
        "maintenance_records": pd.concat(all_maintenance, ignore_index=True),
        "inspection_records": pd.concat(all_inspections, ignore_index=True),
        "downtime_log": pd.concat(all_downtime, ignore_index=True) if all_downtime else pd.DataFrame(),
        "kpi_daily_summary": pd.concat(all_kpis, ignore_index=True),
    }

    for table, df in result.items():
        logger.success(f"  {table}: {len(df):,} records generated")

    logger.info("=" * 60)
    logger.success("Data generation COMPLETE")
    return result


if __name__ == "__main__":
    data = run_full_generation()
