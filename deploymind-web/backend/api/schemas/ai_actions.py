"""Schemas for AI-powered actionable recommendations and executions."""
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List
from datetime import datetime
from enum import Enum


class ActionType(str, Enum):
    """Types of actionable recommendations."""
    SCALE_INSTANCE = "scale_instance"
    STOP_IDLE_DEPLOYMENTS = "stop_idle_deployments"
    TRIGGER_SECURITY_SCAN = "trigger_security_scan"


class ActionStatus(str, Enum):
    """Status of action execution."""
    QUEUED = "queued"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class ActionableRecommendation(BaseModel):
    """
    Structured actionable recommendation from AI services.

    This represents a recommendation that can be executed with a button click.
    """
    id: str = Field(..., description="Unique identifier for this recommendation")
    action_type: ActionType = Field(..., description="Type of action to execute")
    title: str = Field(..., description="Short title (e.g., 'Upgrade to t2.small')")
    description: str = Field(..., description="Detailed explanation of the recommendation")
    parameters: Dict[str, Any] = Field(
        default_factory=dict,
        description="Action-specific parameters (e.g., target_instance_type, deployment_ids)"
    )
    impact: Dict[str, Any] = Field(
        default_factory=dict,
        description="Impact metrics (cost_change_monthly, downtime_minutes, savings_monthly)"
    )
    requires_confirmation: bool = Field(
        default=True,
        description="Whether to show confirmation dialog before execution"
    )
    confirmation_message: str = Field(
        default="Are you sure you want to proceed?",
        description="Message to show in confirmation dialog"
    )
    confidence: str = Field(
        default="high",
        description="AI confidence level (low, medium, high)"
    )
    estimated_duration_minutes: int = Field(
        default=5,
        ge=1,
        le=60,
        description="Estimated time to complete action"
    )
    can_undo: bool = Field(
        default=False,
        description="Whether this action can be reversed"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "id": "scale-inst-abc123",
                "action_type": "scale_instance",
                "title": "Upgrade to t2.small",
                "description": "High CPU usage (75%) requires more resources",
                "parameters": {
                    "deployment_id": "dep-123",
                    "current_instance_type": "t2.micro",
                    "target_instance_type": "t2.small"
                },
                "impact": {
                    "cost_change_monthly": 8.46,
                    "downtime_minutes": 2,
                    "performance_improvement_percent": 50
                },
                "requires_confirmation": True,
                "confirmation_message": "This will stop the instance for ~2 minutes and increase costs by $8.46/month.",
                "confidence": "high",
                "estimated_duration_minutes": 3,
                "can_undo": True
            }
        }


class ActionExecutionRequest(BaseModel):
    """Request to execute an actionable recommendation."""
    recommendation_id: str = Field(..., description="ID of the recommendation to execute")
    parameters: Dict[str, Any] = Field(
        default_factory=dict,
        description="Action parameters (merged with recommendation defaults)"
    )
    confirmed: bool = Field(
        default=False,
        description="User confirmation for destructive actions"
    )


class ActionExecutionResponse(BaseModel):
    """Response after initiating action execution."""
    execution_id: str = Field(..., description="Unique execution ID for status polling")
    status: ActionStatus = Field(..., description="Current execution status")
    message: str = Field(..., description="Human-readable status message")
    estimated_completion_time: Optional[datetime] = Field(
        None,
        description="Estimated completion timestamp"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "execution_id": "exec-xyz789",
                "status": "in_progress",
                "message": "Scaling instance from t2.micro to t2.small...",
                "estimated_completion_time": "2026-02-19T18:15:00Z"
            }
        }


class ActionStatusResponse(BaseModel):
    """Status of an executing or completed action."""
    execution_id: str
    status: ActionStatus
    action_type: ActionType
    progress_percent: int = Field(default=0, ge=0, le=100)
    message: str
    result: Optional[Dict[str, Any]] = Field(
        None,
        description="Result data (available when status=completed)"
    )
    error_message: Optional[str] = Field(
        None,
        description="Error details (available when status=failed)"
    )
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "execution_id": "exec-xyz789",
                "status": "completed",
                "action_type": "scale_instance",
                "progress_percent": 100,
                "message": "Instance successfully scaled to t2.small",
                "result": {
                    "old_instance_type": "t2.micro",
                    "new_instance_type": "t2.small",
                    "downtime_seconds": 87
                },
                "error_message": None,
                "created_at": "2026-02-19T18:10:00Z",
                "started_at": "2026-02-19T18:10:02Z",
                "completed_at": "2026-02-19T18:12:27Z",
                "duration_seconds": 145.3
            }
        }


# Specific action parameter schemas
class ScaleInstanceParams(BaseModel):
    """Parameters for scale_instance action."""
    deployment_id: str
    current_instance_type: str
    target_instance_type: str
    instance_id: str


class StopIdleDeploymentsParams(BaseModel):
    """Parameters for stop_idle_deployments action."""
    deployment_ids: List[str] = Field(..., min_length=1)
    reason: str = Field(default="Idle deployment cleanup")


class TriggerSecurityScanParams(BaseModel):
    """Parameters for trigger_security_scan action."""
    deployment_id: str
    scan_type: str = Field(default="full", pattern="^(full|quick)$")
