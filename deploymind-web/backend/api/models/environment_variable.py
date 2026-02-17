"""Environment variable database model."""
import sys
from pathlib import Path
from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, UniqueConstraint, Index

# Import Base from deploymind-core to share metadata
core_path = Path(__file__).parent.parent.parent.parent / "deploymind-core"
sys.path.insert(0, str(core_path))

try:
    from deploymind.infrastructure.database.connection import Base
except ImportError:
    # Fallback if core not available
    from sqlalchemy.ext.declarative import declarative_base
    Base = declarative_base()


class EnvironmentVariable(Base):
    """
    Environment variables for deployments.

    Stores key-value pairs with encryption support for secrets.
    Ensures no duplicate keys per deployment.
    """

    __tablename__ = "environment_variables"
    __table_args__ = (
        UniqueConstraint('deployment_id', 'key', name='uq_deployment_key'),
        Index('ix_env_vars_deployment_id', 'deployment_id'),
    )

    id = Column(Integer, primary_key=True, index=True)
    deployment_id = Column(String, ForeignKey("deployments.id", ondelete="CASCADE"), nullable=False)
    key = Column(String, nullable=False)
    value = Column(String, nullable=False)  # Encrypted if is_secret=True
    is_secret = Column(Boolean, default=False, nullable=False)

    def __repr__(self):
        masked_value = "***" if self.is_secret else self.value[:20]
        return f"<EnvVar(key={self.key}, value={masked_value})>"
