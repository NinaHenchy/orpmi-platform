"""
ORPMI Platform Setup Script
============================
One-command setup: creates directories, initialises database, runs ETL.
Run this once after cloning the repository.
"""
import sys
from pathlib import Path
for _p in [str(Path(__file__).resolve().parent.parent), "/app"]:
    if _p not in sys.path:
        sys.path.insert(0, _p)



import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))


def main():
    print("=" * 60)
    print("ORPMI Platform — Initial Setup")
    print("=" * 60)

    # Create all required directories
    directories = [
        BASE_DIR / "data" / "raw",
        BASE_DIR / "data" / "processed",
        BASE_DIR / "data" / "exports",
        BASE_DIR / "database",
        BASE_DIR / "logs",
        BASE_DIR / "models",
    ]
    for d in directories:
        d.mkdir(parents=True, exist_ok=True)
        print(f"  ✓ Directory: {d.relative_to(BASE_DIR)}")

    # Initialise database schema
    print("\nInitialising database schema...")
    from database.db_connection import initialize_database, test_connection
    initialize_database()
    test_connection()
    print("  ✓ Database schema created")

    # Run ETL
    print("\nRunning ETL pipeline...")
    from etl.run_etl import run_etl_pipeline
    result = run_etl_pipeline(mode="full_refresh")

    if result["success"]:
        print("\n" + "=" * 60)
        print("✅ Setup Complete — ORPMI Platform is ready.")
        print(f"   Run: streamlit run dashboards/app.py")
        print("=" * 60)
    else:
        print("\n❌ Setup encountered errors. Check logs/")
        sys.exit(1)


if __name__ == "__main__":
    main()
