"""Auto-migration script to add missing columns to database.

This script detects and adds missing columns to existing tables without
dropping data. Run this before starting the application.
"""

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
    print("[ERROR] Could not import deploymind-core models")
    CORE_AVAILABLE = False
    sys.exit(1)


def get_sqlalchemy_type(column):
    """Convert SQLAlchemy column type to PostgreSQL type string."""
    col_type = str(column.type)

    # Map common types
    type_mapping = {
        'VARCHAR': lambda: f"VARCHAR({column.type.length})" if hasattr(column.type, 'length') else "VARCHAR",
        'INTEGER': lambda: 'INTEGER',
        'FLOAT': lambda: 'DOUBLE PRECISION',
        'TIMESTAMP': lambda: 'TIMESTAMP',
        'TEXT': lambda: 'TEXT',
        'BOOLEAN': lambda: 'BOOLEAN',
        'JSON': lambda: 'JSON',
    }

    for key, mapper in type_mapping.items():
        if key in col_type.upper():
            return mapper()

    # Default fallback
    return col_type


def add_missing_columns(db, inspector, table_name, model_class):
    """Add any missing columns to the table."""
    # Get actual columns from database
    db_columns = {col['name'] for col in inspector.get_columns(table_name)}

    # Get expected columns from model
    model_columns = {col.name: col for col in model_class.__table__.columns}

    # Find missing columns
    missing = set(model_columns.keys()) - db_columns

    if missing:
        print(f"\n[MIGRATION] Table: {table_name}")
        for col_name in missing:
            col = model_columns[col_name]
            col_type = get_sqlalchemy_type(col)
            nullable = "NULL" if col.nullable else "NOT NULL"

            # Build ALTER TABLE statement
            alter_sql = f"ALTER TABLE {table_name} ADD COLUMN {col_name} {col_type}"

            # Add default value if specified
            if col.default is not None:
                if isinstance(col.default.arg, str):
                    alter_sql += f" DEFAULT '{col.default.arg}'"
                else:
                    alter_sql += f" DEFAULT {col.default.arg}"

            try:
                db.execute(text(alter_sql))
                print(f"  [+] Added column: {col_name} {col_type}")
            except Exception as e:
                print(f"  [!] Failed to add {col_name}: {e}")
                raise

        db.commit()
        return len(missing)
    return 0


def main():
    """Run auto-migration on all tables."""
    print("=" * 60)
    print("AUTO-MIGRATION: Adding missing columns")
    print("=" * 60)

    db = next(get_db())
    inspector = inspect(db.bind)

    tables_to_check = [
        ('deployments', Deployment),
        ('security_scans', SecurityScan),
        ('build_results', BuildResult),
        ('health_checks', HealthCheck),
        ('deployment_logs', DeploymentLog),
        ('agent_executions', AgentExecution),
    ]

    total_added = 0

    try:
        for table_name, model_class in tables_to_check:
            if table_name in inspector.get_table_names():
                added = add_missing_columns(db, inspector, table_name, model_class)
                total_added += added
            else:
                print(f"[WARNING] Table does not exist: {table_name}")

        print("\n" + "=" * 60)
        if total_added == 0:
            print("[OK] No missing columns detected")
        else:
            print(f"[SUCCESS] Added {total_added} missing column(s)")
        print("=" * 60)

    except Exception as e:
        db.rollback()
        print(f"\n[ERROR] Migration failed: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
