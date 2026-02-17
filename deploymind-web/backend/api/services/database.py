"""Database service to connect deploymind-web to deploymind-core database.

This module provides shared database access for the web API,
connecting to the same PostgreSQL database as deploymind-core.
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from typing import Generator
import sys
from pathlib import Path

# Add deploymind-core to Python path to import its models
core_path = Path(__file__).parent.parent.parent.parent / "deploymind-core"
sys.path.insert(0, str(core_path))

# Import deploymind-core database models
try:
    from deploymind.infrastructure.database.models import (
        Deployment,
        SecurityScan,
        BuildResult,
        HealthCheck,
        DeploymentLog,
        AgentExecution,
    )
    from deploymind.infrastructure.database.connection import Base
except ImportError as e:
    print(f"Warning: Could not import deploymind-core models: {e}")
    print("Using fallback configuration. Some features may not work.")
    Deployment = None
    SecurityScan = None
    BuildResult = None
    HealthCheck = None
    DeploymentLog = None
    AgentExecution = None
    Base = None

from ..config import settings


# Create database engine (shared with deploymind-core)
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
    echo=False,  # Set to True to log SQL queries
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """
    Dependency for FastAPI routes to get database session.

    Usage:
        @router.get("/items")
        async def get_items(db: Session = Depends(get_db)):
            items = db.query(Item).all()
            return items

    Yields:
        Session: SQLAlchemy database session
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_web_db():
    """
    Initialize database tables for web-specific models.

    Note: Core deploymind tables (deployments, security_scans, etc.)
    are created by deploymind-core. This only creates web-specific tables.
    """
    from ..models.user import User
    from ..models.environment_variable import EnvironmentVariable

    # Create web-specific tables
    User.__table__.create(bind=engine, checkfirst=True)
    EnvironmentVariable.__table__.create(bind=engine, checkfirst=True)

    print("✓ Web database tables initialized")


def check_db_connection() -> bool:
    """
    Check if database connection is working.

    Returns:
        bool: True if connection successful, False otherwise
    """
    try:
        from sqlalchemy import text
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        return True
    except Exception as e:
        print(f"Database connection failed: {e}")
        return False


# Export commonly used models for convenience
__all__ = [
    "get_db",
    "init_web_db",
    "check_db_connection",
    "SessionLocal",
    "engine",
    "Deployment",
    "SecurityScan",
    "BuildResult",
    "HealthCheck",
    "DeploymentLog",
    "AgentExecution",
]
