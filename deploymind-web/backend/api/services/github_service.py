"""GitHub repository browsing and integration service."""
import sys
from pathlib import Path
from typing import List, Dict, Optional
import logging

# Initialize logger first
logger = logging.getLogger(__name__)

# Import PyGithub directly (required)
try:
    from github import Github, GithubException
    PYGITHUB_AVAILABLE = True
    logger.info("[GITHUB] PyGithub successfully imported")
except ImportError as e:
    PYGITHUB_AVAILABLE = False
    logger.error(f"[GITHUB] Failed to import PyGithub: {e}")
    logger.error(f"[GITHUB] Make sure PyGithub is installed: pip install PyGithub")
    Github = None
    GithubException = Exception

# Optional: Try to import deploymind-core (not required for basic functionality)
try:
    core_path = Path(__file__).parent.parent.parent.parent / "deploymind-core"
    sys.path.insert(0, str(core_path))
    from deploymind.infrastructure.vcs.github.github_client import GitHubClient
    from deploymind.config.settings import Settings as CoreSettings
    CORE_AVAILABLE = True
    logger.info("[GITHUB] deploymind-core successfully imported")
except ImportError as e:
    logger.warning(f"[GITHUB] deploymind-core not available (optional): {e}")
    GitHubClient = None
    CoreSettings = None
    CORE_AVAILABLE = False

from api.services.database import get_db
from api.models.user import User


class GitHubService:
    """Service for GitHub repository operations."""

    def __init__(self):
        """Initialize GitHub service."""
        # Optional: Initialize core client if available (for fallback token)
        if CORE_AVAILABLE and GitHubClient and CoreSettings:
            try:
                settings = CoreSettings.load()
                self.client = GitHubClient(settings)
                logger.info("[GITHUB] Core GitHubClient initialized (fallback token available)")
            except Exception as e:
                logger.warning(f"[GITHUB] Failed to initialize core GitHubClient: {e}")
                self.client = None
        else:
            logger.info("[GITHUB] Core GitHubClient not available (user tokens only)")
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
        logger.info(f"[GITHUB] search_user_repositories called for user_id={user_id}, query='{query}'")

        if not PYGITHUB_AVAILABLE or not Github:
            logger.error("[GITHUB] PyGithub not available, returning mock data")
            return self._mock_repositories(query)

        try:
            # Get user's GitHub access token from database
            logger.info(f"[GITHUB] Fetching user {user_id} from database")
            db = next(get_db())
            user = db.query(User).get(user_id)

            if not user:
                logger.error(f"[GITHUB] User {user_id} not found in database")
                return []

            logger.info(f"[GITHUB] Found user: {user.username} (github_id={user.github_id})")

            if not user.github_id:
                logger.error(f"[GITHUB] User {user.username} has no GitHub ID")
                return []

            # Use user's personal GitHub access token (IMPORTANT!)
            # Fallback to core token if user token not available
            token = user.github_access_token if hasattr(user, 'github_access_token') and user.github_access_token else None

            logger.info(f"[GITHUB] User token status: {'SET (length=' + str(len(token)) + ')' if token else 'NULL'}")

            if not token and self.client:
                token = self.client.settings.github_token
                logger.warning(f"[GITHUB] No user token, using fallback token for user {user_id}")

            if not token:
                logger.error("[GITHUB] No GitHub token available (neither user token nor fallback)")
                return []

            logger.info(f"[GITHUB] Initializing GitHub client with token")
            github = Github(token)

            # Get authenticated user (the owner of the token)
            logger.info(f"[GITHUB] Getting authenticated GitHub user")
            authenticated_user = github.get_user()
            logger.info(f"[GITHUB] Authenticated as: {authenticated_user.login}")

            # Fetch ALL repositories using PyGithub's pagination
            # According to PyGithub docs: get_repos() returns a PaginatedList
            # We should iterate through it or convert to list
            logger.info(f"[GITHUB] Fetching repositories (type='all', sort='updated')")

            repos_paginated = authenticated_user.get_repos(
                type='all',  # Get all repos (owned, member, org)
                sort='updated',  # Sort by recently updated
            )

            # Convert PaginatedList to regular list (fetches all pages)
            logger.info(f"[GITHUB] Converting paginated list to list (this may take a moment)...")
            all_repos = list(repos_paginated)

            logger.info(f"[GITHUB] Successfully fetched {len(all_repos)} repositories for user {user.username}")

            # Filter by query
            if query:
                original_count = len(all_repos)
                all_repos = [r for r in all_repos if query.lower() in r.name.lower() or query.lower() in r.full_name.lower()]
                logger.info(f"[GITHUB] Filtered by query '{query}': {original_count} -> {len(all_repos)} repos")

            # Sort by updated_at (most recent first)
            all_repos.sort(key=lambda r: r.updated_at, reverse=True)

            result = [
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
                for repo in all_repos
            ]

            logger.info(f"[GITHUB] Returning {len(result)} repositories")
            if result:
                logger.info(f"[GITHUB] First 3 repos: {[r['full_name'] for r in result[:3]]}")

            return result

        except GithubException as e:
            logger.error(f"[GITHUB] GitHub API error: {e.status} - {e.data}")
            logger.error(f"[GITHUB] Full exception: {str(e)}")
            import traceback
            logger.error(f"[GITHUB] Traceback:\n{traceback.format_exc()}")
            return self._mock_repositories(query)
        except Exception as e:
            logger.error(f"[GITHUB] Unexpected error: {type(e).__name__}: {str(e)}")
            import traceback
            logger.error(f"[GITHUB] Traceback:\n{traceback.format_exc()}")
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
