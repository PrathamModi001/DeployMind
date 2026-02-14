"""User database model."""
from sqlalchemy import Column, Integer, String, DateTime, Boolean
from sqlalchemy.sql import func
from datetime import datetime


try:
    # Import from existing infrastructure
    import sys
    from pathlib import Path

    # Add parent directories to path
    backend_dir = Path(__file__).parent.parent.parent
    sys.path.insert(0, str(backend_dir.parent))

    from infrastructure.database.connection import Base
except ImportError:
    # Fallback if infrastructure not available
    from sqlalchemy.ext.declarative import declarative_base
    Base = declarative_base()


class User(Base):
    """User model for authentication."""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    is_superuser = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
