"""Dependency injection container.

This module wires together all layers of the application following
the Dependency Inversion Principle of Clean Architecture.
"""

from deploymind.config.settings import settings
from deploymind.infrastructure.cloud.aws.ec2_client import EC2Client
from deploymind.infrastructure.vcs.github.github_client import GitHubClient
from deploymind.infrastructure.cache.redis_client import RedisClient
from deploymind.infrastructure.llm.groq.groq_client import GroqClient
from deploymind.infrastructure.database.repositories.deployment_repo_impl import DeploymentRepositoryImpl
from deploymind.infrastructure.database.repositories.security_scan_repo_impl import SecurityScanRepositoryImpl
from deploymind.infrastructure.database.repositories.build_result_repo_impl import BuildResultRepositoryImpl
from deploymind.infrastructure.database.repositories.health_check_repo_impl import HealthCheckRepositoryImpl


class DependencyContainer:
    """Container for dependency injection.

    This class initializes and holds all infrastructure dependencies
    and makes them available to application use cases and agents.
    """

    def __init__(self):
        """Initialize all dependencies."""
        # Infrastructure layer - External services
        self.ec2_client = EC2Client(settings)
        self.github_client = GitHubClient(settings)
        self.redis_client = RedisClient(settings.redis_url)
        self.groq_client = GroqClient(settings.groq_api_key)

        # Infrastructure layer - Repositories
        self.deployment_repo = DeploymentRepositoryImpl()
        self.security_scan_repo = SecurityScanRepositoryImpl()
        self.build_result_repo = BuildResultRepositoryImpl()
        self.health_check_repo = HealthCheckRepositoryImpl()

    def validate_all(self) -> bool:
        """Validate all external service connections.

        Returns:
            True if all services are accessible.
        """
        results = {
            "AWS": self.ec2_client.validate_credentials(),
            "GitHub": self.github_client.validate_token(),
        }

        all_valid = all(results.values())

        if all_valid:
            print("[OK] All dependencies validated successfully")
        else:
            failed = [name for name, valid in results.items() if not valid]
            print(f"[ERROR] Failed validations: {', '.join(failed)}")

        return all_valid


# Global container instance
container = DependencyContainer()
