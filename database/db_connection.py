"""
ORPMI Database Connection Manager
Handles SQLite (dev) and PostgreSQL (prod) connections via SQLAlchemy.
"""

import sqlite3
from pathlib import Path
from contextlib import contextmanager

from sqlalchemy import create_engine, text, event
from sqlalchemy.orm import sessionmaker
from loguru import logger

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config.settings import SQLITE_DB_PATH, DB_TYPE, POSTGRES_URL


def get_engine():
    if DB_TYPE == "sqlite":
        engine = create_engine(
            f"sqlite:///{SQLITE_DB_PATH}",
            connect_args={"check_same_thread": False},
            echo=False,
        )
        # Enable WAL mode for SQLite — improves concurrent read performance
        @event.listens_for(engine, "connect")
        def set_sqlite_pragma(dbapi_conn, connection_record):
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA cache_size=-64000")  # 64MB cache
            cursor.close()
    else:
        engine = create_engine(
            POSTGRES_URL,
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,
            echo=False,
        )

    logger.info(f"Database engine created: {DB_TYPE.upper()}")
    return engine


def get_session_factory(engine=None):
    if engine is None:
        engine = get_engine()
    return sessionmaker(bind=engine, autocommit=False, autoflush=False)


@contextmanager
def get_db_connection():
    """Context manager: yields a raw SQLite connection for bulk ETL operations."""
    conn = sqlite3.connect(str(SQLITE_DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"Database error: {e}")
        raise
    finally:
        conn.close()


def initialize_database():
    """Create all tables from schema SQL file."""
    schema_path = Path(__file__).parent / "schemas" / "orpmi_schema.sql"
    engine = get_engine()

    with engine.connect() as conn:
        sql_text = schema_path.read_text()
        # Execute each statement separately
        statements = [s.strip() for s in sql_text.split(";") if s.strip() and not s.strip().startswith("--")]
        for stmt in statements:
            if stmt:
                try:
                    conn.execute(text(stmt))
                except Exception as e:
                    if "already exists" not in str(e).lower():
                        logger.warning(f"Schema statement warning: {e}")
        conn.commit()

    logger.success("Database schema initialised successfully.")
    return engine


def test_connection():
    engine = get_engine()
    with engine.connect() as conn:
        result = conn.execute(text("SELECT 1"))
        logger.success(f"Database connection test PASSED — {DB_TYPE.upper()}")
    return True


if __name__ == "__main__":
    initialize_database()
    test_connection()
