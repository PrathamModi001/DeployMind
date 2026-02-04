"""Deploy application use case."""

from domain.repositories.deployment_repository import DeploymentRepository
from application.interfaces.cloud_service import CloudService


class DeployApplication:
    """Use case for deploying an application."""

    def __init__(
        self,
        deployment_repo: DeploymentRepository,
        cloud_service: CloudService
    ):
        self.deployment_repo = deployment_repo
        self.cloud_service = cloud_service

    def execute(self, repo: str, instance_id: str) -> str:
        """Execute deployment use case."""
        # TODO: Implement deployment logic
        raise NotImplementedError("Will be implemented in Day 2-5")
