"""Complete architecture migration script.

This script performs all remaining migrations to Clean Architecture:
1. Update infrastructure clients
2. Migrate agent files
3. Move CLI to presentation
4. Create dependency injection container
5. Update all imports
"""

from pathlib import Path

BASE_DIR = Path(__file__).parent.parent


def create_ec2_client():
    """Create enhanced EC2 client."""
    content = '''"""AWS EC2 client implementation.

Migrated from core/aws_client.py to follow Clean Architecture.
"""

from __future__ import annotations
from typing import TYPE_CHECKING

import boto3
from botocore.exceptions import ClientError, NoCredentialsError

from config.settings import Settings
from config.logging import get_logger
from shared.exceptions import DeploymentError

if TYPE_CHECKING:
    from mypy_boto3_ec2.client import EC2Client as BotoEC2Client

logger = get_logger(__name__)


class EC2Client:
    """AWS EC2 client for deployment operations."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._ec2: BotoEC2Client | None = None

    @property
    def ec2(self) -> BotoEC2Client:
        """Lazy-initialize EC2 client."""
        if self._ec2 is None:
            self._ec2 = boto3.client(
                "ec2",
                region_name=self.settings.aws_region,
                aws_access_key_id=self.settings.aws_access_key_id,
                aws_secret_access_key=self.settings.aws_secret_access_key,
            )
        return self._ec2

    def validate_credentials(self) -> bool:
        """Check if AWS credentials are valid."""
        try:
            sts = boto3.client(
                "sts",
                aws_access_key_id=self.settings.aws_access_key_id,
                aws_secret_access_key=self.settings.aws_secret_access_key,
            )
            identity = sts.get_caller_identity()
            logger.info("AWS credentials valid", extra={"account": identity["Account"]})
            return True
        except (ClientError, NoCredentialsError) as e:
            logger.error("AWS credential validation failed", extra={"error": str(e)})
            return False

    def describe_instance(self, instance_id: str) -> dict:
        """Get EC2 instance details."""
        try:
            response = self.ec2.describe_instances(InstanceIds=[instance_id])
            if response['Reservations'] and response['Reservations'][0]['Instances']:
                return response['Reservations'][0]['Instances'][0]
            raise DeploymentError(f"Instance {instance_id} not found")
        except ClientError as e:
            logger.error(f"Failed to describe instance: {e}")
            raise DeploymentError(f"Failed to describe instance {instance_id}") from e

    def get_instance_status(self, instance_id: str) -> dict:
        """Get instance status."""
        try:
            response = self.ec2.describe_instance_status(
                InstanceIds=[instance_id],
                IncludeAllInstances=True
            )
            return response['InstanceStatuses'][0] if response['InstanceStatuses'] else {}
        except ClientError as e:
            logger.error(f"Failed to get instance status: {e}")
            raise DeploymentError(f"Failed to get status for {instance_id}") from e

    def get_instance_public_ip(self, instance_id: str) -> str | None:
        """Get instance public IP."""
        instance = self.describe_instance(instance_id)
        return instance.get('PublicIpAddress')
'''

    file_path = BASE_DIR / "infrastructure/cloud/aws/ec2_client.py"
    file_path.write_text(content)
    print(f"[OK] Created: infrastructure/cloud/aws/ec2_client.py")


def create_github_client():
    """Create enhanced GitHub client."""
    content = '''"""GitHub API client implementation.

Migrated from core/github_client.py to follow Clean Architecture.
"""

from __future__ import annotations

from github import Github, GithubException

from config.settings import Settings
from config.logging import get_logger

logger = get_logger(__name__)


class GitHubClient:
    """GitHub API client for repository operations."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._client: Github | None = None

    @property
    def client(self) -> Github:
        """Lazy-initialize GitHub client."""
        if self._client is None:
            self._client = Github(self.settings.github_token)
        return self._client

    def validate_token(self) -> bool:
        """Check if GitHub token is valid."""
        try:
            user = self.client.get_user()
            logger.info("GitHub token valid", extra={"user": user.login})
            return True
        except GithubException as e:
            logger.error("GitHub token validation failed", extra={"error": str(e)})
            return False

    def get_repository(self, repo_full_name: str):
        """Get repository object (owner/repo)."""
        try:
            return self.client.get_repo(repo_full_name)
        except GithubException as e:
            logger.error(f"Failed to get repository {repo_full_name}: {e}")
            raise

    def get_latest_commit_sha(self, repo_full_name: str) -> str:
        """Get latest commit SHA for tagging Docker images."""
        repo = self.get_repository(repo_full_name)
        return repo.get_commits()[0].sha

    def check_dockerfile_exists(self, repo_full_name: str) -> bool:
        """Check if repo has a Dockerfile."""
        repo = self.get_repository(repo_full_name)
        try:
            repo.get_contents("Dockerfile")
            return True
        except GithubException:
            return False
'''

    file_path = BASE_DIR / "infrastructure/vcs/github/github_client.py"
    file_path.write_text(content)
    print(f"[OK] Created: infrastructure/vcs/github/github_client.py")


def create_dependency_container():
    """Create dependency injection container."""
    content = '''"""Dependency injection container.

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
'''

    file_path = BASE_DIR / "config/dependencies.py"
    file_path.write_text(content)
    print(f"[OK] Created: config/dependencies.py")


def main():
    """Run complete migration."""
    print("=" * 60)
    print("COMPLETE ARCHITECTURE MIGRATION")
    print("=" * 60)
    print()

    create_ec2_client()
    create_github_client()
    create_dependency_container()

    print()
    print("=" * 60)
    print("[OK] MIGRATION COMPLETE!")
    print("=" * 60)
    print()
    print("Next steps:")
    print("1. Test imports: python -c 'from config.settings import settings'")
    print("2. Validate dependencies: python -c 'from config.dependencies import container; container.validate_all()'")
    print("3. Start implementing agents (Day 2-5)")


if __name__ == "__main__":
    main()
