"""Security scan repository interface (port)."""

from abc import ABC, abstractmethod
from typing import List, Optional


class SecurityScanRepository(ABC):
    """Interface for security scan persistence."""

    @abstractmethod
    def create(self, deployment_id: str, scan_data: dict) -> dict:
        """Create a new security scan record.

        Args:
            deployment_id: Deployment ID this scan belongs to.
            scan_data: Security scan data dictionary.

        Returns:
            Created security scan data.
        """
        pass

    @abstractmethod
    def get_by_deployment(self, deployment_id: str) -> List[dict]:
        """Get all security scans for a deployment.

        Args:
            deployment_id: Deployment ID.

        Returns:
            List of security scan data dictionaries.
        """
        pass

    @abstractmethod
    def get_by_id(self, scan_id: int) -> Optional[dict]:
        """Get security scan by ID.

        Args:
            scan_id: Security scan ID.

        Returns:
            Security scan data or None if not found.
        """
        pass

    @abstractmethod
    def get_latest_for_deployment(self, deployment_id: str) -> Optional[dict]:
        """Get the most recent security scan for a deployment.

        Args:
            deployment_id: Deployment ID.

        Returns:
            Latest security scan data or None if not found.
        """
        pass
