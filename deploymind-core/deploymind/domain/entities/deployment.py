"""Deployment entity - core business object."""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class Deployment:
    """Represents a deployment in the system."""

    id: str
    repository: str
    instance_id: str
    status: str  # Will be DeploymentStatus enum
    created_at: datetime
    updated_at: Optional[datetime] = None
    image_tag: Optional[str] = None

    def can_rollback(self) -> bool:
        """Business rule: Can only rollback deployed/failed deployments."""
        return self.status in ["deployed", "failed"]
