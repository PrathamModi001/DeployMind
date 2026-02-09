"""GitHub API client implementation.

Migrated from core/github_client.py to follow Clean Architecture.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path

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

    def clone_repository(self, repo_full_name: str, target_dir: str | None = None) -> str:
        """Clone GitHub repository to local directory.

        Args:
            repo_full_name: Repository in format "owner/repo"
            target_dir: Target directory path. If None, creates temp directory.

        Returns:
            Path to cloned repository

        Raises:
            subprocess.CalledProcessError: If git clone fails
            GithubException: If repository doesn't exist
        """
        # Validate repository exists
        repo = self.get_repository(repo_full_name)
        clone_url = repo.clone_url

        # Use temp directory if not specified
        if target_dir is None:
            target_dir = tempfile.mkdtemp(prefix=f"deploymind-{repo.name}-")
        else:
            # Clean up existing directory if it exists
            if os.path.exists(target_dir):
                import shutil
                logger.info(f"Removing existing directory: {target_dir}")
                try:
                    shutil.rmtree(target_dir, ignore_errors=True)
                except Exception as e:
                    logger.warning(f"Could not remove directory: {e}")

            # Ensure parent directory exists
            parent_dir = os.path.dirname(target_dir)
            os.makedirs(parent_dir, exist_ok=True)

        # Clone using git command
        logger.info(f"Cloning repository {repo_full_name} to {target_dir}")

        try:
            # Use HTTPS URL with token for authentication
            auth_url = clone_url.replace(
                "https://",
                f"https://{self.settings.github_token}@"
            )

            subprocess.run(
                ["git", "clone", auth_url, target_dir],
                check=True,
                capture_output=True,
                text=True
            )

            logger.info(f"Successfully cloned {repo_full_name}", extra={
                "repo": repo_full_name,
                "path": target_dir
            })

            return target_dir

        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to clone repository: {e.stderr}")
            raise
        except FileNotFoundError:
            logger.error("git command not found. Please install git.")
            raise RuntimeError("git is not installed or not in PATH")

    def get_file_content(self, repo_full_name: str, file_path: str) -> str:
        """Get content of a file from repository.

        Args:
            repo_full_name: Repository in format "owner/repo"
            file_path: Path to file in repository

        Returns:
            File content as string
        """
        repo = self.get_repository(repo_full_name)
        try:
            content = repo.get_contents(file_path)
            return content.decoded_content.decode('utf-8')
        except GithubException as e:
            logger.error(f"Failed to get file {file_path}: {e}")
            raise
