"""Build result repository interface (port)."""

from abc import ABC, abstractmethod
from typing import List, Optional


class BuildResultRepository(ABC):
    """Interface for build result persistence."""

    @abstractmethod
    def create(self, deployment_id: str, build_data: dict) -> dict:
        """Create a new build result record.

        Args:
            deployment_id: Deployment ID this build belongs to.
            build_data: Build result data dictionary.

        Returns:
            Created build result data.
        """
        pass

    @abstractmethod
    def get_by_deployment(self, deployment_id: str) -> List[dict]:
        """Get all build results for a deployment.

        Args:
            deployment_id: Deployment ID.

        Returns:
            List of build result data dictionaries.
        """
        pass

    @abstractmethod
    def get_by_id(self, build_id: int) -> Optional[dict]:
        """Get build result by ID.

        Args:
            build_id: Build result ID.

        Returns:
            Build result data or None if not found.
        """
        pass

    @abstractmethod
    def get_latest_for_deployment(self, deployment_id: str) -> Optional[dict]:
        """Get the most recent build result for a deployment.

        Args:
            deployment_id: Deployment ID.

        Returns:
            Latest build result data or None if not found.
        """
        pass
