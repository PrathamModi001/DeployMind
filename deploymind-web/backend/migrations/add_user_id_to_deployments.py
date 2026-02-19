"""Add user_id column to deployments table.

This migration adds the user_id column to track which user created each deployment.
"""

from sqlalchemy import text
from api.services.database import get_db


def upgrade():
    """Add user_id column to deployments table."""
    db = next(get_db())

    try:
        # Check if column exists
        result = db.execute(text("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name='deployments' AND column_name='user_id'
        """))

        if result.fetchone() is None:
            # Add user_id column
            db.execute(text("""
                ALTER TABLE deployments
                ADD COLUMN user_id INTEGER
            """))
            db.commit()
            print("[SUCCESS] Added user_id column to deployments table")
        else:
            print("[INFO] user_id column already exists")

    except Exception as e:
        db.rollback()
        print(f"[ERROR] Migration failed: {e}")
        raise
    finally:
        db.close()


def downgrade():
    """Remove user_id column from deployments table."""
    db = next(get_db())

    try:
        db.execute(text("""
            ALTER TABLE deployments
            DROP COLUMN IF EXISTS user_id
        """))
        db.commit()
        print("[SUCCESS] Removed user_id column from deployments table")

    except Exception as e:
        db.rollback()
        print(f"[ERROR] Rollback failed: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    print("Running migration: add_user_id_to_deployments")
    upgrade()
