"""Deployment status value object."""

from enum import Enum


class DeploymentStatus(str, Enum):
    """Possible deployment statuses."""

    PENDING = "pending"
    SECURITY_SCANNING = "security_scanning"
    BUILDING = "building"
    DEPLOYING = "deploying"
    DEPLOYED = "deployed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"
