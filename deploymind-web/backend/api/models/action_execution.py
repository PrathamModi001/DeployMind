"""Action execution model for tracking AI recommendation executions."""
import sys
from pathlib import Path
from sqlalchemy import Column, Integer, String, DateTime, Text, JSON, ForeignKey, Enum as SQLEnum
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import enum

# Import Base from deploymind-core to share metadata
core_path = Path(__file__).parent.parent.parent.parent / "deploymind-core"
sys.path.insert(0, str(core_path))

try:
    from deploymind.infrastructure.database.connection import Base
except ImportError:
    # Fallback if core not available
    from sqlalchemy.ext.declarative import declarative_base
    Base = declarative_base()


class ActionStatusEnum(enum.Enum):
    """Action execution status enum."""
    QUEUED = "queued"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class ActionTypeEnum(enum.Enum):
    """Action type enum."""
    SCALE_INSTANCE = "scale_instance"
    STOP_IDLE_DEPLOYMENTS = "stop_idle_deployments"
    TRIGGER_SECURITY_SCAN = "trigger_security_scan"


class ActionExecution(Base):
    """
    Track execution of AI-powered actionable recommendations.

    Records when users execute AI recommendations (scale instance,
    stop idle deployments, trigger scans) with full audit trail.
    """

    __tablename__ = "action_executions"

    id = Column(String, primary_key=True, index=True)  # UUID format: exec-{uuid}
    user_id = Column(Integer, ForeignKey("web_users.id"), nullable=False, index=True)
    deployment_id = Column(String, nullable=True, index=True)  # Optional, not all actions target specific deployment

    # Action details
    action_type = Column(SQLEnum(ActionTypeEnum), nullable=False, index=True)
    status = Column(SQLEnum(ActionStatusEnum), default=ActionStatusEnum.QUEUED, nullable=False, index=True)

    # Parameters and results
    parameters = Column(JSON, nullable=False)  # Action-specific parameters
    result = Column(JSON, nullable=True)  # Result data (available when completed)
    error_message = Column(Text, nullable=True)  # Error details (available when failed)

    # Progress tracking
    progress_percent = Column(Integer, default=0, nullable=False)
    current_step = Column(String, nullable=True)  # Current step description

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    user = relationship("User", foreign_keys=[user_id])

    def __repr__(self):
        return f"<ActionExecution(id={self.id}, action_type={self.action_type.value}, status={self.status.value})>"

    @property
    def duration_seconds(self) -> float | None:
        """Calculate execution duration in seconds."""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None
