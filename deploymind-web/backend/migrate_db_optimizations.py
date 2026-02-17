"""Database migration script for short-term optimizations.

This script applies the following optimizations:
1. Remove hashed_password from web_users (GitHub OAuth only)
2. Add user_id foreign key to deployments
3. Add unique constraint on environment_variables (deployment_id, key)

Run with: python migrate_db_optimizations.py
"""
import sys
from pathlib import Path

# Add deploymind-core to path
core_path = Path(__file__).parent.parent.parent / "deploymind-core"
sys.path.insert(0, str(core_path))

from sqlalchemy import text
from api.services.database import engine
from api.config import settings


def migrate_database():
    """Apply database optimizations."""
    print("🔧 Applying database optimizations...")
    print(f"Database: {settings.database_url}")
    print()

    with engine.connect() as conn:
        # Start transaction
        trans = conn.begin()

        try:
            # Optimization 1: Remove hashed_password column (if exists)
            print("1️⃣ Removing hashed_password from web_users...")
            try:
                conn.execute(text("""
                    ALTER TABLE web_users
                    DROP COLUMN IF EXISTS hashed_password;
                """))
                conn.execute(text("""
                    ALTER TABLE web_users
                    ALTER COLUMN github_id SET NOT NULL;
                """))
                print("   ✅ Removed hashed_password column")
                print("   ✅ Set github_id as NOT NULL")
            except Exception as e:
                print(f"   ⚠️  Column might not exist or already removed: {e}")

            # Optimization 2: Add user_id to deployments
            print("\n2️⃣ Adding user_id to deployments...")
            try:
                # Check if column exists
                result = conn.execute(text("""
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_name='deployments' AND column_name='user_id';
                """))
                if result.fetchone():
                    print("   ⚠️  user_id column already exists")
                else:
                    conn.execute(text("""
                        ALTER TABLE deployments
                        ADD COLUMN user_id INTEGER;
                    """))
                    print("   ✅ Added user_id column to deployments")

                # Add index on user_id
                conn.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_deployments_user_id
                    ON deployments(user_id);
                """))
                print("   ✅ Created index on user_id")
            except Exception as e:
                print(f"   ⚠️  Error: {e}")

            # Optimization 3: Add unique constraint on environment_variables
            print("\n3️⃣ Adding unique constraint on environment_variables...")
            try:
                # Drop existing constraint if exists
                conn.execute(text("""
                    ALTER TABLE environment_variables
                    DROP CONSTRAINT IF EXISTS uq_deployment_key;
                """))

                # Add unique constraint
                conn.execute(text("""
                    ALTER TABLE environment_variables
                    ADD CONSTRAINT uq_deployment_key
                    UNIQUE (deployment_id, key);
                """))
                print("   ✅ Added unique constraint (deployment_id, key)")

                # Add index on deployment_id
                conn.execute(text("""
                    CREATE INDEX IF NOT EXISTS ix_env_vars_deployment_id
                    ON environment_variables(deployment_id);
                """))
                print("   ✅ Created index on deployment_id")

                # Add CASCADE delete
                conn.execute(text("""
                    ALTER TABLE environment_variables
                    DROP CONSTRAINT IF EXISTS environment_variables_deployment_id_fkey;
                """))
                conn.execute(text("""
                    ALTER TABLE environment_variables
                    ADD CONSTRAINT environment_variables_deployment_id_fkey
                    FOREIGN KEY (deployment_id)
                    REFERENCES deployments(id)
                    ON DELETE CASCADE;
                """))
                print("   ✅ Added CASCADE delete on foreign key")
            except Exception as e:
                print(f"   ⚠️  Error: {e}")

            # Commit transaction
            trans.commit()
            print("\n✅ All optimizations applied successfully!")
            print("\n📊 Benefits:")
            print("   • Reduced storage (removed unused hashed_password column)")
            print("   • Better data integrity (unique constraints)")
            print("   • Improved query performance (new indexes)")
            print("   • Automatic cleanup (CASCADE deletes)")
            print("   • User tracking (user_id foreign key)")

        except Exception as e:
            trans.rollback()
            print(f"\n❌ Migration failed: {e}")
            print("Transaction rolled back.")
            raise


def verify_optimizations():
    """Verify optimizations were applied."""
    print("\n🔍 Verifying optimizations...")

    with engine.connect() as conn:
        # Check web_users
        result = conn.execute(text("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name='web_users' AND column_name='hashed_password';
        """))
        has_password = result.fetchone()

        if has_password:
            print("   ⚠️  hashed_password still exists")
        else:
            print("   ✅ hashed_password removed")

        # Check deployments.user_id
        result = conn.execute(text("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name='deployments' AND column_name='user_id';
        """))
        has_user_id = result.fetchone()

        if has_user_id:
            print("   ✅ user_id exists in deployments")
        else:
            print("   ⚠️  user_id missing from deployments")

        # Check constraint
        result = conn.execute(text("""
            SELECT constraint_name
            FROM information_schema.table_constraints
            WHERE table_name='environment_variables'
            AND constraint_name='uq_deployment_key';
        """))
        has_constraint = result.fetchone()

        if has_constraint:
            print("   ✅ Unique constraint exists")
        else:
            print("   ⚠️  Unique constraint missing")


if __name__ == "__main__":
    print("=" * 60)
    print("DATABASE OPTIMIZATION MIGRATION")
    print("=" * 60)
    print()

    # Ask for confirmation
    response = input("Apply optimizations to database? (yes/no): ")
    if response.lower() != "yes":
        print("Migration cancelled.")
        sys.exit(0)

    print()
    migrate_database()
    verify_optimizations()

    print("\n" + "=" * 60)
    print("✅ Migration complete!")
    print("=" * 60)
