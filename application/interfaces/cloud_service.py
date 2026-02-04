"""Cloud service interface."""

from abc import ABC, abstractmethod


class CloudService(ABC):
    """Interface for cloud operations."""

    @abstractmethod
    def deploy_container(self, instance_id: str, image: str) -> bool:
        """Deploy container to instance."""
        pass

    @abstractmethod
    def check_instance_status(self, instance_id: str) -> dict:
        """Check instance health."""
        pass
