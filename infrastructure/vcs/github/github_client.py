"""GitHub API client implementation.

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
