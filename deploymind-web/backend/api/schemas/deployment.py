"""Deployment schemas for API requests/responses."""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum


class EnvVarCreate(BaseModel):
    """Schema for an environment variable."""
    key: str
    value: str
    is_secret: bool = False


class DeploymentStatus(str, Enum):
    """Deployment status enum."""
    PENDING = "PENDING"
    SECURITY_SCANNING = "SECURITY_SCANNING"
    BUILDING = "BUILDING"
    DEPLOYING = "DEPLOYING"
    DEPLOYED = "DEPLOYED"
    FAILED = "FAILED"
    ROLLED_BACK = "ROLLED_BACK"


class DeploymentCreate(BaseModel):
    """Schema for creating a new deployment."""
    repository: str = Field(..., description="GitHub repository (owner/repo)")
    instance_id: str = Field(..., pattern=r"^i-[a-f0-9]{8,17}$", description="EC2 instance ID")
    port: int = Field(default=8080, ge=1, le=65535)
    strategy: str = Field(default="rolling", pattern="^(rolling|blue-green|canary)$")
    health_check_path: str = Field(default="/health")
    environment: str = Field(default="production", pattern="^(development|staging|production)$")
    env_vars: Optional[List[EnvVarCreate]] = None


class DeploymentResponse(BaseModel):
    """Schema for deployment response."""
    id: str
    repository: str
    instance_id: str
    commit_sha: Optional[str] = None
    status: DeploymentStatus
    image_tag: Optional[str] = None
    port: int
    strategy: str
    environment: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None

    class Config:
        from_attributes = True


class DeploymentListResponse(BaseModel):
    """Paginated deployment list response."""
    total: int
    page: int
    page_size: int
    deployments: list[DeploymentResponse]
