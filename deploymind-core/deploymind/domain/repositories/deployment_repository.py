"""Deployment repository interface (port)."""

from abc import ABC, abstractmethod
from typing import List, Optional
from deploymind.domain.entities.deployment import Deployment


class DeploymentRepository(ABC):
    """Interface for deployment persistence."""

    @abstractmethod
    def create(self, deployment: Deployment) -> Deployment:
        """Create a new deployment."""
        pass

    @abstractmethod
    def get_by_id(self, deployment_id: str) -> Optional[Deployment]:
        """Get deployment by ID."""
        pass

    @abstractmethod
    def update(self, deployment: Deployment) -> Deployment:
        """Update existing deployment."""
        pass

    @abstractmethod
    def list_all(self) -> List[Deployment]:
        """List all deployments."""
        pass
