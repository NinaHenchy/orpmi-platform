"""
ORPMI ETL Pipeline Orchestrator
================================
Coordinates the full Extract → Validate → Load pipeline.
Designed to be scheduled (cron/Airflow) or run manually.
Produces an ETL run log saved to /logs/.
"""

import sys
import json
from pathlib import Path
from datetime import datetime

from loguru import logger

# Configure logging
LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)
log_file = LOG_DIR / f"etl_run_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
logger.add(log_file, rotation="10 MB", retention="30 days", level="DEBUG")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from database.db_connection import initialize_database, get_engine, test_connection
from etl.extractors.synthetic_data_generator import run_full_generation
from etl.validators.data_validator import run_full_validation
from etl.loaders.db_loader import load_all_tables, verify_load


def run_etl_pipeline(mode: str = "full_refresh") -> dict:
    """
    Main ETL entry point.
    mode: 'full_refresh' = drop and reload all data
          'incremental'  = append new records (future use)
    """
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    start_time = datetime.now()

    logger.info("=" * 70)
    logger.info("ORPMI ETL PIPELINE — RUN STARTED")
    logger.info(f"Run ID    : {run_id}")
    logger.info(f"Mode      : {mode.upper()}")
    logger.info(f"Start Time: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 70)

    pipeline_result = {
        "run_id": run_id,
        "mode": mode,
        "start_time": start_time.isoformat(),
        "stages": {},
        "success": False,
    }

    # ── STAGE 1: Database Initialisation ──────────────────────────────────
    logger.info("\n[STAGE 1] Database Initialisation")
    try:
        engine = initialize_database()
        test_connection()
        pipeline_result["stages"]["db_init"] = "PASS"
        logger.success("  Database ready.")
    except Exception as e:
        logger.critical(f"  Database initialisation FAILED: {e}")
        pipeline_result["stages"]["db_init"] = f"FAIL: {e}"
        return pipeline_result

    # ── STAGE 2: Data Extraction ───────────────────────────────────────────
    logger.info("\n[STAGE 2] Data Extraction — Synthetic Generation")
    try:
        datasets = run_full_generation()
        total_records = sum(len(df) for df in datasets.values())
        pipeline_result["stages"]["extraction"] = {
            "status": "PASS",
            "total_records_generated": total_records,
            "tables": {k: len(v) for k, v in datasets.items()},
        }
        logger.success(f"  Extraction complete: {total_records:,} total records across {len(datasets)} tables")
    except Exception as e:
        logger.critical(f"  Extraction FAILED: {e}")
        pipeline_result["stages"]["extraction"] = f"FAIL: {e}"
        return pipeline_result

    # ── STAGE 3: Data Validation ───────────────────────────────────────────
    logger.info("\n[STAGE 3] Data Validation")
    try:
        validation_report = run_full_validation(datasets)
        validation_df = validation_report.to_dataframe()

        # Save validation report to CSV
        val_report_path = LOG_DIR / f"validation_report_{run_id}.csv"
        validation_df.to_csv(val_report_path, index=False)

        if not validation_report.passed:
            critical_fails = [r.check_name for r in validation_report.critical_failures]
            logger.error(f"  Validation FAILURES: {critical_fails}")
            pipeline_result["stages"]["validation"] = {
                "status": "FAIL",
                "critical_failures": critical_fails,
            }
            return pipeline_result

        pipeline_result["stages"]["validation"] = {
            "status": "PASS",
            "total_checks": len(validation_report.results),
            "warnings": len(validation_report.warnings),
            "report_path": str(val_report_path),
        }
        logger.success(f"  Validation PASSED — {validation_report.summary()}")
    except Exception as e:
        logger.critical(f"  Validation FAILED: {e}")
        pipeline_result["stages"]["validation"] = f"FAIL: {e}"
        return pipeline_result

    # ── STAGE 4: Data Loading ──────────────────────────────────────────────
    logger.info("\n[STAGE 4] Database Load")
    try:
        load_mode = "replace" if mode == "full_refresh" else "append"
        load_summary = load_all_tables(datasets, engine, mode=load_mode)
        pipeline_result["stages"]["loading"] = {
            "status": "PASS",
            "tables_loaded": load_summary,
        }
        logger.success(f"  Load complete: {sum(load_summary.values()):,} total rows written")
    except Exception as e:
        logger.critical(f"  Loading FAILED: {e}")
        pipeline_result["stages"]["loading"] = f"FAIL: {e}"
        return pipeline_result

    # ── STAGE 5: Verification ──────────────────────────────────────────────
    logger.info("\n[STAGE 5] Post-Load Verification")
    try:
        verify_df = verify_load(engine)
        pipeline_result["stages"]["verification"] = {
            "status": "PASS",
            "row_counts": verify_df.to_dict(orient="records"),
        }
        logger.success("  Verification PASSED — all tables confirmed.")
    except Exception as e:
        logger.warning(f"  Verification issue: {e}")
        pipeline_result["stages"]["verification"] = f"WARN: {e}"

    # ── STAGE 6: Export CSVs ───────────────────────────────────────────────
    logger.info("\n[STAGE 6] Export processed datasets to CSV")
    try:
        processed_dir = Path(__file__).resolve().parent.parent / "data" / "processed"
        processed_dir.mkdir(parents=True, exist_ok=True)
        for table_name, df in datasets.items():
            if not df.empty:
                out_path = processed_dir / f"{table_name}.csv"
                df.to_csv(out_path, index=False)
        logger.success(f"  CSV exports written to {processed_dir}")
        pipeline_result["stages"]["csv_export"] = "PASS"
    except Exception as e:
        logger.warning(f"  CSV export issue: {e}")
        pipeline_result["stages"]["csv_export"] = f"WARN: {e}"

    # ── PIPELINE COMPLETE ──────────────────────────────────────────────────
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    pipeline_result["success"] = True
    pipeline_result["end_time"] = end_time.isoformat()
    pipeline_result["duration_seconds"] = round(duration, 2)

    # Save run log JSON
    log_json_path = LOG_DIR / f"etl_run_summary_{run_id}.json"
    with open(log_json_path, "w") as f:
        json.dump(pipeline_result, f, indent=2, default=str)

    logger.info("\n" + "=" * 70)
    logger.success("ORPMI ETL PIPELINE — COMPLETE")
    logger.info(f"Run ID   : {run_id}")
    logger.info(f"Duration : {duration:.1f} seconds")
    logger.info(f"Status   : SUCCESS")
    logger.info(f"Log      : {log_file}")
    logger.info("=" * 70)

    return pipeline_result


if __name__ == "__main__":
    result = run_etl_pipeline(mode="full_refresh")
    if result["success"]:
        print("\n✅ ETL Pipeline completed successfully.")
        print(f"   Duration: {result.get('duration_seconds', 0):.1f}s")
        print(f"   Log:      logs/")
    else:
        print("\n❌ ETL Pipeline FAILED. Check logs for details.")
        sys.exit(1)
