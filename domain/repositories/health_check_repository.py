"""Health check repository interface (port)."""

from abc import ABC, abstractmethod
from typing import List, Optional


class HealthCheckRepository(ABC):
    """Interface for health check persistence."""

    @abstractmethod
    def create(self, deployment_id: str, check_data: dict) -> dict:
        """Create a new health check record.

        Args:
            deployment_id: Deployment ID this check belongs to.
            check_data: Health check data dictionary.

        Returns:
            Created health check data.
        """
        pass

    @abstractmethod
    def get_by_deployment(self, deployment_id: str) -> List[dict]:
        """Get all health checks for a deployment.

        Args:
            deployment_id: Deployment ID.

        Returns:
            List of health check data dictionaries.
        """
        pass

    @abstractmethod
    def get_by_id(self, check_id: int) -> Optional[dict]:
        """Get health check by ID.

        Args:
            check_id: Health check ID.

        Returns:
            Health check data or None if not found.
        """
        pass

    @abstractmethod
    def get_latest_for_deployment(self, deployment_id: str) -> Optional[dict]:
        """Get the most recent health check for a deployment.

        Args:
            deployment_id: Deployment ID.

        Returns:
            Latest health check data or None if not found.
        """
        pass

    @abstractmethod
    def get_failed_checks(self, deployment_id: str) -> List[dict]:
        """Get all failed health checks for a deployment.

        Args:
            deployment_id: Deployment ID.

        Returns:
            List of failed health check data dictionaries.
        """
        pass
