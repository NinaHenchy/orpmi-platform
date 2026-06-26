"""
ORPMI Database Loader
=====================
Loads validated DataFrames into the SQLite/PostgreSQL database.
Uses upsert logic to support incremental ETL runs.
"""

import sys
from pathlib import Path

import pandas as pd
from loguru import logger
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from database.db_connection import get_engine


TABLE_LOAD_ORDER = [
    "assets",
    "asset_operating_data",
    "failure_events",
    "maintenance_records",
    "inspection_records",
    "downtime_log",
    "kpi_daily_summary",
]


def load_table(df: pd.DataFrame, table_name: str, engine, if_exists: str = "append") -> int:
    """Load a single DataFrame into the database."""
    if df is None or df.empty:
        logger.warning(f"  Skipping {table_name} — empty DataFrame")
        return 0

    # For replace mode, truncate first then insert
    if if_exists == "replace":
        try:
            with engine.connect() as conn:
                conn.execute(text(f"DELETE FROM {table_name}"))
                conn.commit()
        except Exception:
            pass  # Table may not exist yet on first run
        if_exists = "append"

    rows_before = len(df)
    try:
        df.to_sql(
            table_name,
            con=engine,
            if_exists=if_exists,
            index=False,
            chunksize=500,
            method="multi",
        )
        logger.success(f"  Loaded {table_name}: {rows_before:,} rows")
        return rows_before
    except Exception as e:
        logger.error(f"  FAILED to load {table_name}: {e}")
        raise


def load_all_tables(datasets: dict, engine=None, mode: str = "replace") -> dict:
    """
    Load all datasets in dependency order.
    mode='replace': truncate and reload (full refresh ETL run)
    mode='append': add new records only (incremental)
    """
    if engine is None:
        engine = get_engine()

    summary = {}
    for table_name in TABLE_LOAD_ORDER:
        if table_name in datasets:
            count = load_table(datasets[table_name], table_name, engine, if_exists=mode)
            summary[table_name] = count
        else:
            logger.warning(f"  {table_name} not found in datasets — skipping")

    return summary


def verify_load(engine=None) -> pd.DataFrame:
    """Run row count verification across all tables post-load."""
    if engine is None:
        engine = get_engine()

    rows = []
    with engine.connect() as conn:
        for table_name in TABLE_LOAD_ORDER:
            try:
                result = conn.execute(text(f"SELECT COUNT(*) FROM {table_name}"))
                count = result.scalar()
                rows.append({"table": table_name, "row_count": count, "status": "OK"})
                logger.success(f"  Verify {table_name}: {count:,} rows")
            except Exception as e:
                rows.append({"table": table_name, "row_count": 0, "status": f"ERROR: {e}"})
                logger.error(f"  Verify FAILED {table_name}: {e}")

    return pd.DataFrame(rows)


if __name__ == "__main__":
    from etl.extractors.synthetic_data_generator import run_full_generation
    from database.db_connection import initialize_database

    initialize_database()
    data = run_full_generation()
    engine = get_engine()
    load_all_tables(data, engine, mode="replace")
    verify_load(engine)
