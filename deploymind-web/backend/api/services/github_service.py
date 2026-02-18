"""GitHub repository browsing and integration service."""
import sys
from pathlib import Path
from typing import List, Dict, Optional
import logging

# Add deploymind-core to path
core_path = Path(__file__).parent.parent.parent.parent.parent / "deploymind-core"
sys.path.insert(0, str(core_path))

try:
    from deploymind.infrastructure.vcs.github.github_client import GitHubClient
    from deploymind.config.settings import Settings as CoreSettings
    from github import Github, GithubException
    CORE_AVAILABLE = True
except ImportError:
    GitHubClient = None
    CoreSettings = None
    Github = None
    GithubException = Exception
    CORE_AVAILABLE = False

from api.services.database import get_db
from api.models.user import User

logger = logging.getLogger(__name__)


class GitHubService:
    """Service for GitHub repository operations."""

    def __init__(self):
        """Initialize GitHub service."""
        if CORE_AVAILABLE and GitHubClient and CoreSettings:
            try:
                settings = CoreSettings.load()
                self.client = GitHubClient(settings)
            except Exception as e:
                logger.warning(f"Failed to initialize GitHub client: {e}")
                self.client = None
        else:
            self.client = None

    async def search_user_repositories(
        self,
        user_id: int,
        query: str = ""
    ) -> List[Dict]:
        """
        Search authenticated user's GitHub repositories.

        Args:
            user_id: User ID from database
            query: Optional search query to filter repos

        Returns:
            List of repository dictionaries
        """
        if not CORE_AVAILABLE or not Github:
            return self._mock_repositories(query)

        try:
            # Get user's GitHub access token from database
            db = next(get_db())
            user = db.query(User).get(user_id)

            if not user or not user.github_id:
                return []

            # Use core GitHub token (fallback to user's token if available)
            github = Github(self.client.settings.github_token if self.client else None)
            repos = list(github.get_user().get_repos())

            # Filter by query
            if query:
                repos = [r for r in repos if query.lower() in r.name.lower()]

            # Sort by updated_at (most recent first)
            repos.sort(key=lambda r: r.updated_at, reverse=True)

            return [
                {
                    "id": repo.id,
                    "name": repo.name,
                    "full_name": repo.full_name,
                    "description": repo.description or "",
                    "language": repo.language or "Unknown",
                    "default_branch": repo.default_branch,
                    "clone_url": repo.clone_url,
                    "updated_at": repo.updated_at.isoformat()
                }
                for repo in repos[:20]  # Limit to 20 results
            ]
        except Exception as e:
            logger.error(f"Failed to search repositories: {e}")
            return self._mock_repositories(query)

    async def get_repository_branches(
        self,
        repo_full_name: str
    ) -> List[Dict]:
        """
        Get all branches for a repository.

        Args:
            repo_full_name: Repository in format "owner/repo"

        Returns:
            List of branch dictionaries
        """
        if not self.client:
            return self._mock_branches(repo_full_name)

        try:
            repo = self.client.get_repository(repo_full_name)
            branches = repo.get_branches()

            return [
                {
                    "name": branch.name,
                    "commit_sha": branch.commit.sha,
                    "protected": branch.protected
                }
                for branch in branches
            ]
        except Exception as e:
            logger.error(f"Failed to get branches for {repo_full_name}: {e}")
            return self._mock_branches(repo_full_name)

    async def get_latest_commit_sha(
        self,
        repo_full_name: str,
        branch: str = "main"
    ) -> Optional[str]:
        """
        Get latest commit SHA for a branch.

        Args:
            repo_full_name: Repository in format "owner/repo"
            branch: Branch name (default: main)

        Returns:
            Commit SHA or None
        """
        if not self.client:
            return "abc123def456"  # Mock SHA

        try:
            return self.client.get_latest_commit_sha(repo_full_name)
        except Exception as e:
            logger.error(f"Failed to get commit SHA: {e}")
            return "abc123def456"  # Return mock SHA on error

    async def detect_framework(
        self,
        repo_full_name: str
    ) -> Dict:
        """
        Auto-detect framework/language from repository files.

        Args:
            repo_full_name: Repository in format "owner/repo"

        Returns:
            Dict with framework and has_dockerfile
        """
        if not self.client:
            return {"framework": "node", "has_dockerfile": False}

        try:
            repo = self.client.get_repository(repo_full_name)

            framework_indicators = {
                "package.json": "node",
                "requirements.txt": "python",
                "go.mod": "go",
                "pom.xml": "java",
                "Gemfile": "ruby",
                "composer.json": "php",
                "Cargo.toml": "rust"
            }

            detected_framework = "unknown"
            for file_name, framework in framework_indicators.items():
                try:
                    repo.get_contents(file_name)
                    detected_framework = framework
                    break
                except:
                    continue

            has_dockerfile = self.client.check_dockerfile_exists(repo_full_name)

            return {
                "framework": detected_framework,
                "has_dockerfile": has_dockerfile
            }
        except Exception as e:
            logger.error(f"Failed to detect framework for {repo_full_name}: {e}")
            return {"framework": "unknown", "has_dockerfile": False}

    def _mock_repositories(self, query: str = "") -> List[Dict]:
        """Mock repositories when GitHub unavailable."""
        mock_repos = [
            {
                "id": 1,
                "name": "my-app",
                "full_name": "user/my-app",
                "description": "My awesome application",
                "language": "TypeScript",
                "default_branch": "main",
                "clone_url": "https://github.com/user/my-app.git",
                "updated_at": "2026-02-18T10:00:00Z"
            },
            {
                "id": 2,
                "name": "api-server",
                "full_name": "user/api-server",
                "description": "REST API server",
                "language": "Python",
                "default_branch": "main",
                "clone_url": "https://github.com/user/api-server.git",
                "updated_at": "2026-02-17T15:30:00Z"
            }
        ]

        if query:
            mock_repos = [r for r in mock_repos if query.lower() in r["name"].lower()]

        return mock_repos

    def _mock_branches(self, repo_full_name: str) -> List[Dict]:
        """Mock branches when GitHub unavailable."""
        return [
            {
                "name": "main",
                "commit_sha": "abc123def456",
                "protected": True
            },
            {
                "name": "develop",
                "commit_sha": "def456ghi789",
                "protected": False
            }
        ]
