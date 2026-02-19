"""User database model for web authentication."""
import sys
from pathlib import Path
from sqlalchemy import Column, Integer, String, DateTime, Boolean
from sqlalchemy.sql import func

# Import Base from deploymind-core to share metadata
core_path = Path(__file__).parent.parent.parent.parent / "deploymind-core"
sys.path.insert(0, str(core_path))

try:
    from deploymind.infrastructure.database.connection import Base
except ImportError:
    # Fallback if core not available
    from sqlalchemy.ext.declarative import declarative_base
    Base = declarative_base()


class User(Base):
    """
    User model for authentication and authorization.

    GitHub OAuth only - no password authentication.
    """

    __tablename__ = "web_users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    username = Column(String, unique=True, index=True, nullable=False)
    full_name = Column(String, nullable=True)

    # OAuth fields (GitHub only)
    github_id = Column(String, unique=True, nullable=False, index=True)
    github_access_token = Column(String, nullable=True)  # User's GitHub access token
    avatar_url = Column(String, nullable=True)

    # Status fields
    is_active = Column(Boolean, default=True, nullable=False)
    is_superuser = Column(Boolean, default=False, nullable=False)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self):
        return f"<User(id={self.id}, email={self.email}, username={self.username})>"
