"""Dependency injection container.

This module wires together all layers of the application following
the Dependency Inversion Principle of Clean Architecture.
"""

from config.settings import settings
from infrastructure.cloud.aws.ec2_client import EC2Client
from infrastructure.vcs.github.github_client import GitHubClient
from infrastructure.cache.redis_client import RedisClient
from infrastructure.llm.groq.groq_client import GroqClient


class DependencyContainer:
    """Container for dependency injection.

    This class initializes and holds all infrastructure dependencies
    and makes them available to application use cases and agents.
    """

    def __init__(self):
        """Initialize all dependencies."""
        # Infrastructure layer
        self.ec2_client = EC2Client(settings)
        self.github_client = GitHubClient(settings)
        self.redis_client = RedisClient(settings.redis_url)
        self.groq_client = GroqClient(settings.groq_api_key)

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
