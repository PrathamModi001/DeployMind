"""Script to reorganize DeployMind to Clean Architecture.

Run this to migrate from flat structure to layered architecture.
"""

import os
import shutil
from pathlib import Path

# Base directory
BASE_DIR = Path(__file__).parent.parent

# New directory structure
NEW_STRUCTURE = {
    "domain": [
        "entities",
        "value_objects",
        "repositories",
        "services"
    ],
    "application": [
        "use_cases",
        "dto",
        "interfaces"
    ],
    "infrastructure": [
        "database",
        "database/repositories",
        "cloud",
        "cloud/aws",
        "cloud/adapters",
        "vcs",
        "vcs/github",
        "vcs/adapters",
        "cache",
        "llm",
        "llm/groq",
        "llm/adapters",
        "security",
        "containers"
    ],
    "agents": [
        "base",
        "security",
        "build",
        "deploy",
        "orchestrator"
    ],
    "presentation": [
        "cli",
        "cli/commands",
        "cli/formatters",
        "api",
        "api/routes",
        "api/middleware"
    ],
    "config": [],
    "shared": [],
    "scripts": [],
    "tests": [
        "unit",
        "unit/domain",
        "unit/application",
        "unit/infrastructure",
        "integration",
        "e2e"
    ]
}

def create_init_file(directory: Path):
    """Create __init__.py in a directory."""
    init_file = directory / "__init__.py"
    if not init_file.exists():
        init_file.write_text('"""Package initialization."""\n')
        print(f"  Created: {init_file.relative_to(BASE_DIR)}")

def create_directory_structure():
    """Create the new Clean Architecture directory structure."""
    print("Creating new directory structure...\n")

    for top_level, subdirs in NEW_STRUCTURE.items():
        top_path = BASE_DIR / top_level
        top_path.mkdir(exist_ok=True)
        create_init_file(top_path)
        print(f"[OK] Created: {top_level}/")

        for subdir in subdirs:
            sub_path = BASE_DIR / top_level / subdir
            sub_path.mkdir(parents=True, exist_ok=True)
            create_init_file(sub_path)
            print(f"  [OK] Created: {top_level}/{subdir}/")

def create_placeholder_files():
    """Create placeholder files with docstrings."""
    print("\n\nCreating placeholder files...\n")

    placeholders = {
        # Domain layer
        "domain/entities/deployment.py": '''"""Deployment entity - core business object."""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class Deployment:
    """Represents a deployment in the system."""

    id: str
    repository: str
    instance_id: str
    status: str  # Will be DeploymentStatus enum
    created_at: datetime
    updated_at: Optional[datetime] = None
    image_tag: Optional[str] = None

    def can_rollback(self) -> bool:
        """Business rule: Can only rollback deployed/failed deployments."""
        return self.status in ["deployed", "failed"]
''',

        "domain/value_objects/deployment_status.py": '''"""Deployment status value object."""

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
''',

        "domain/repositories/deployment_repository.py": '''"""Deployment repository interface (port)."""

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
''',

        # Application layer
        "application/use_cases/deploy_application.py": '''"""Deploy application use case."""

from deploymind.domain.repositories.deployment_repository import DeploymentRepository
from deploymind.application.interfaces.cloud_service import CloudService


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
''',

        "application/interfaces/cloud_service.py": '''"""Cloud service interface."""

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
''',

        # Infrastructure layer
        "infrastructure/cloud/aws/ec2_client.py": '''"""AWS EC2 client implementation."""

import boto3
from deploymind.application.interfaces.cloud_service import CloudService


class EC2Client(CloudService):
    """AWS EC2 implementation of CloudService."""

    def __init__(self, access_key: str, secret_key: str, region: str):
        self.client = boto3.client(
            'ec2',
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region
        )

    def deploy_container(self, instance_id: str, image: str) -> bool:
        """Deploy container to EC2 instance."""
        # TODO: Implement via SSM or SSH
        raise NotImplementedError("Will be implemented in Day 4")

    def check_instance_status(self, instance_id: str) -> dict:
        """Check EC2 instance status."""
        response = self.client.describe_instance_status(
            InstanceIds=[instance_id]
        )
        return response
''',

        "infrastructure/vcs/github/github_client.py": '''"""GitHub client implementation."""

from github import Github


class GitHubClient:
    """GitHub API client."""

    def __init__(self, token: str):
        self.client = Github(token)

    def get_repository(self, repo_full_name: str):
        """Get repository object."""
        return self.client.get_repo(repo_full_name)

    def get_latest_commit_sha(self, repo_full_name: str) -> str:
        """Get latest commit SHA."""
        repo = self.get_repository(repo_full_name)
        return repo.get_commits()[0].sha
''',

        "infrastructure/cache/redis_client.py": '''"""Redis cache client."""

import redis
import json


class RedisClient:
    """Redis client for caching and pub/sub."""

    def __init__(self, redis_url: str):
        self.client = redis.from_url(redis_url)

    def set_deployment_status(self, deployment_id: str, status: str):
        """Set deployment status in cache."""
        self.client.set(f"deployment:{deployment_id}:status", status)

    def get_deployment_status(self, deployment_id: str) -> str:
        """Get deployment status from cache."""
        status = self.client.get(f"deployment:{deployment_id}:status")
        return status.decode() if status else None

    def publish_event(self, channel: str, message: dict):
        """Publish event to Redis channel."""
        self.client.publish(channel, json.dumps(message))
''',

        "infrastructure/llm/groq/groq_client.py": '''"""Groq LLM client."""

from groq import Groq


class GroqClient:
    """Groq API client for LLM operations."""

    def __init__(self, api_key: str):
        self.client = Groq(api_key=api_key)

    def chat_completion(self, model: str, messages: list) -> str:
        """Get chat completion from Groq."""
        response = self.client.chat.completions.create(
            model=model,
            messages=messages
        )
        return response.choices[0].message.content
''',

        # Config
        "config/settings.py": '''"""Application settings and configuration."""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)


class Settings:
    """Application settings loaded from environment variables."""

    # Groq API
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    DEFAULT_LLM: str = os.getenv("DEFAULT_LLM", "llama-3.1-70b-versatile")
    COST_SAVING_LLM: str = os.getenv("COST_SAVING_LLM", "llama-3.1-8b-instant")

    # AWS
    AWS_ACCESS_KEY_ID: str = os.getenv("AWS_ACCESS_KEY_ID", "")
    AWS_SECRET_ACCESS_KEY: str = os.getenv("AWS_SECRET_ACCESS_KEY", "")
    AWS_REGION: str = os.getenv("AWS_REGION", "us-east-1")

    # GitHub
    GITHUB_TOKEN: str = os.getenv("GITHUB_TOKEN", "")

    # Database
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql://admin:password@localhost:5432/deploymind"
    )

    # Redis
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379")

    # Application
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    @classmethod
    def validate(cls) -> list[str]:
        """Validate required settings."""
        required = {
            "GROQ_API_KEY": cls.GROQ_API_KEY,
            "AWS_ACCESS_KEY_ID": cls.AWS_ACCESS_KEY_ID,
            "AWS_SECRET_ACCESS_KEY": cls.AWS_SECRET_ACCESS_KEY,
            "GITHUB_TOKEN": cls.GITHUB_TOKEN,
        }
        return [name for name, value in required.items() if not value]


settings = Settings()
''',

        "shared/exceptions.py": '''"""Custom exceptions for DeployMind."""


class DeployMindException(Exception):
    """Base exception for DeployMind."""
    pass


class DeploymentError(DeployMindException):
    """Deployment-related errors."""
    pass


class SecurityScanError(DeployMindException):
    """Security scanning errors."""
    pass


class BuildError(DeployMindException):
    """Build-related errors."""
    pass


class ConfigurationError(DeployMindException):
    """Configuration errors."""
    pass
''',
    }

    for file_path, content in placeholders.items():
        full_path = BASE_DIR / file_path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content)
        print(f"[OK] Created: {file_path}")

def move_existing_files():
    """Move existing files to new locations."""
    print("\n\nMoving existing files...\n")

    migrations = {
        # Keep core/config.py for now (will merge with config/settings.py later)
        "core/logger.py": "config/logging.py",

        # Move scripts
        "verify_all_credentials.py": "scripts/verify_all_credentials.py",
    }

    for old_path_str, new_path_str in migrations.items():
        old_path = BASE_DIR / old_path_str
        new_path = BASE_DIR / new_path_str

        if old_path.exists():
            new_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(old_path, new_path)
            print(f"[OK] Moved: {old_path_str} -> {new_path_str}")

def main():
    """Run the reorganization."""
    print("="*60)
    print("DEPLOYMIND ARCHITECTURE REORGANIZATION")
    print("Clean Architecture (Layered) Implementation")
    print("="*60 + "\n")

    create_directory_structure()
    create_placeholder_files()
    move_existing_files()

    print("\n" + "="*60)
    print("[OK] REORGANIZATION COMPLETE!")
    print("="*60)
    print("\nNext steps:")
    print("1. Review ARCHITECTURE.md for layer explanations")
    print("2. Update imports in existing agent files")
    print("3. Move agent files to agents/* subdirectories")
    print("4. Implement remaining infrastructure clients")
    print("5. Run tests: pytest tests/")

if __name__ == "__main__":
    main()
