"""GitHub API wrapper for DeployMind."""

from __future__ import annotations

from github import Github, GithubException

from core.config import Config
from core.logger import get_logger

logger = get_logger(__name__)


class GitHubClient:
    """Wrapper around PyGithub for repository operations."""

    def __init__(self, config: Config) -> None:
        self.config = config
        self._client: Github | None = None

    @property
    def client(self) -> Github:
        """Lazy-initialize GitHub client."""
        if self._client is None:
            self._client = Github(self.config.github_token)
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

    def get_repo(self, repo_full_name: str):
        """Get a GitHub repository by full name (owner/repo)."""
        raise NotImplementedError("Will be implemented on Day 2")

    def get_latest_commit(self, repo_full_name: str, branch: str = "main") -> dict:
        """Get the latest commit from a repository branch."""
        raise NotImplementedError("Will be implemented on Day 2")

    def clone_repo(self, repo_full_name: str, target_dir: str) -> str:
        """Clone a repository to a local directory."""
        raise NotImplementedError("Will be implemented on Day 2")
