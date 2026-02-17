"""Initialize database tables for deploymind-web and deploymind-core.

Run this script to create all necessary database tables.
"""
import sys
from pathlib import Path

# Add deploymind-core to path
core_path = Path(__file__).parent.parent.parent / "deploymind-core"
sys.path.insert(0, str(core_path))

from api.services.database import check_db_connection, engine

def main():
    print("Checking database connection...")

    if not check_db_connection():
        print("ERROR: Database connection failed!")
        print("Make sure PostgreSQL is running and DATABASE_URL is correct in .env")
        return

    print("SUCCESS: Database connection successful!")

    print("\nInitializing database tables...")
    try:
        # Step 1: Create deploymind-core tables first
        print("\nStep 1: Creating deploymind-core tables...")
        try:
            from deploymind.infrastructure.database.connection import init_db as init_core_db
            init_core_db()
            print("SUCCESS: Core tables created (deployments, security_scans, build_results, health_checks, deployment_logs)")
        except ImportError:
            print("WARNING: Could not import deploymind-core, creating tables manually...")
            from deploymind.infrastructure.database.models import Base
            Base.metadata.create_all(bind=engine)
            print("SUCCESS: Core tables created via Base.metadata")

        # Step 2: Create deploymind-web tables
        print("\nStep 2: Creating deploymind-web tables...")
        from api.models.user import User
        from api.models.environment_variable import EnvironmentVariable

        User.__table__.create(bind=engine, checkfirst=True)
        print("  - web_users created")

        EnvironmentVariable.__table__.create(bind=engine, checkfirst=True)
        print("  - environment_variables created")

        print("\nSUCCESS: Database initialization complete!")
        print("\nAll tables created:")
        print("  Core tables (deploymind-core):")
        print("    - deployments")
        print("    - security_scans")
        print("    - build_results")
        print("    - health_checks")
        print("    - deployment_logs")
        print("  Web tables (deploymind-web):")
        print("    - web_users")
        print("    - environment_variables")

    except Exception as e:
        print(f"\nERROR: Database initialization failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
