"""Database connection and session management.

Provides SQLAlchemy engine and session factory for database operations.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from contextlib import contextmanager

from deploymind.config.settings import settings
from deploymind.infrastructure.database.models import Base
from deploymind.config.logging import get_logger

logger = get_logger(__name__)


# Create engine
engine = create_engine(
    settings.database_url,
    echo=settings.is_development,  # Log SQL in development
    pool_pre_ping=True,  # Verify connections before using
    pool_size=5,
    max_overflow=10
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    """Initialize database by creating all tables.

    This should be called once when the application starts.
    """
    logger.info("Initializing database...")
    Base.metadata.create_all(bind=engine)
    logger.info("Database initialized successfully")


def drop_all_tables():
    """Drop all tables.

    WARNING: This will delete all data! Only use in development/testing.
    """
    if not settings.is_development:
        raise RuntimeError("Cannot drop tables in production!")

    logger.warning("Dropping all database tables...")
    Base.metadata.drop_all(bind=engine)
    logger.warning("All tables dropped")


@contextmanager
def get_db() -> Session:
    """Get database session with automatic cleanup.

    Usage:
        with get_db() as db:
            deployment = db.query(Deployment).first()

    Yields:
        SQLAlchemy session.
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def get_db_session() -> Session:
    """Get a database session (manual management).

    Note: You must close this session manually!

    Returns:
        SQLAlchemy session.
    """
    return SessionLocal()
