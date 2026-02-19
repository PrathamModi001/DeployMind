"""Check database schema against models and report any missing columns."""

import sys
from pathlib import Path

# Add deploymind-core to path
core_path = Path(__file__).parent.parent.parent.parent / "deploymind-core"
sys.path.insert(0, str(core_path))

from api.services.database import get_db
from sqlalchemy import inspect, text

try:
    from deploymind.infrastructure.database.models import (
        Deployment, SecurityScan, BuildResult, HealthCheck,
        DeploymentLog, AgentExecution
    )
    CORE_AVAILABLE = True
except ImportError:
    print("[WARNING] Could not import deploymind-core models")
    CORE_AVAILABLE = False


def check_table_columns(inspector, table_name, model_class):
    """Check if all model columns exist in database."""
    # Get actual columns from database
    db_columns = {col['name'] for col in inspector.get_columns(table_name)}

    # Get expected columns from model
    model_columns = {col.name for col in model_class.__table__.columns}

    # Find missing columns
    missing = model_columns - db_columns
    extra = db_columns - model_columns

    if missing or extra:
        print(f"\n[CHECK] Table: {table_name}")
        if missing:
            print(f"  Missing columns: {', '.join(missing)}")
        if extra:
            print(f"  Extra columns: {', '.join(extra)}")
        return False
    else:
        print(f"[OK] Table: {table_name} - all columns match")
        return True


def main():
    """Check all tables against models."""
    if not CORE_AVAILABLE:
        print("[ERROR] Cannot check schema without deploymind-core models")
        return

    db = next(get_db())
    inspector = inspect(db.bind)

    print("=" * 60)
    print("DATABASE SCHEMA CHECK")
    print("=" * 60)

    all_ok = True

    # Check each table
    tables_to_check = [
        ('deployments', Deployment),
        ('security_scans', SecurityScan),
        ('build_results', BuildResult),
        ('health_checks', HealthCheck),
        ('deployment_logs', DeploymentLog),
        ('agent_executions', AgentExecution),
    ]

    for table_name, model_class in tables_to_check:
        if table_name in inspector.get_table_names():
            if not check_table_columns(inspector, table_name, model_class):
                all_ok = False
        else:
            print(f"[ERROR] Table missing: {table_name}")
            all_ok = False

    print("\n" + "=" * 60)
    if all_ok:
        print("[SUCCESS] All tables and columns are in sync")
    else:
        print("[WARNING] Schema issues detected - may need migration")
    print("=" * 60)

    db.close()


if __name__ == "__main__":
    main()
