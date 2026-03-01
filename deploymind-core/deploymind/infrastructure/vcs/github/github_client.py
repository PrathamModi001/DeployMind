"""GitHub API client implementation.

Migrated from core/github_client.py to follow Clean Architecture.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path

from github import Github, GithubException

from deploymind.config.settings import Settings
from deploymind.config.logging import get_logger

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

    def post_deployment_status(
        self,
        repo_full_name: str,
        commit_sha: str,
        state: str,
        description: str,
        context: str = "deploymind/deployment",
        target_url: str = "",
    ) -> None:
        """Post a commit status check to GitHub.

        Args:
            repo_full_name: Repository in format "owner/repo"
            commit_sha: Full commit SHA to update
            state: One of "pending", "success", "failure", "error"
            description: Short human-readable description (max 140 chars)
            context: Status context identifier (defaults to deploymind/deployment)
            target_url: Optional URL to link from the status (e.g. build logs)
        """
        _VALID_STATES = {"pending", "success", "failure", "error"}
        if state not in _VALID_STATES:
            raise ValueError(f"state must be one of {_VALID_STATES}, got {state!r}")

        repo = self.get_repository(repo_full_name)
        commit = repo.get_commit(commit_sha)
        kwargs: dict = dict(
            state=state,
            description=description[:140],  # GitHub limit
            context=context,
        )
        if target_url:
            kwargs["target_url"] = target_url

        try:
            commit.create_status(**kwargs)
            logger.info(
                "Posted commit status",
                extra={"repo": repo_full_name, "sha": commit_sha[:7], "state": state},
            )
        except GithubException as e:
            logger.error(f"Failed to post commit status: {e}")
            raise

    def create_pr_comment(
        self,
        repo_full_name: str,
        pr_number: int,
        body: str,
    ) -> None:
        """Add a comment to a pull request.

        Args:
            repo_full_name: Repository in format "owner/repo"
            pr_number: Pull request number
            body: Markdown-formatted comment body
        """
        repo = self.get_repository(repo_full_name)
        try:
            pr = repo.get_pull(pr_number)
            pr.create_issue_comment(body)
            logger.info(
                "Created PR comment",
                extra={"repo": repo_full_name, "pr": pr_number},
            )
        except GithubException as e:
            logger.error(f"Failed to create PR comment: {e}")
            raise

    def get_pr_for_branch(self, repo_full_name: str, branch: str) -> int | None:
        """Find the open pull request number for a given head branch.

        Args:
            repo_full_name: Repository in format "owner/repo"
            branch: Head branch name (e.g. "feature/my-feature")

        Returns:
            PR number if an open PR exists for that branch, otherwise None.
        """
        repo = self.get_repository(repo_full_name)
        try:
            pulls = repo.get_pulls(state="open", head=f"{repo.owner.login}:{branch}")
            for pr in pulls:
                return pr.number  # Return first matching open PR
            return None
        except GithubException as e:
            logger.error(f"Failed to look up PR for branch {branch}: {e}")
            raise
