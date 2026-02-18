"""GitHub repository integration endpoints."""
from fastapi import APIRouter, Depends, Query
from typing import List, Dict

from api.middleware.auth import get_current_active_user
from api.services.github_service import GitHubService

router = APIRouter(prefix="/api/github", tags=["github"])


@router.get("/repositories")
async def list_repositories(
    query: str = Query("", description="Search query to filter repositories"),
    current_user: dict = Depends(get_current_active_user)
):
    """
    List user's GitHub repositories with optional search.

    Args:
        query: Optional search query to filter by repo name
        current_user: Authenticated user

    Returns:
        List of repositories
    """
    service = GitHubService()
    repos = await service.search_user_repositories(current_user["id"], query)

    return {"repositories": repos}


@router.get("/repositories/{owner}/{repo}/branches")
async def list_branches(
    owner: str,
    repo: str,
    current_user: dict = Depends(get_current_active_user)
):
    """
    List all branches for a repository.

    Args:
        owner: Repository owner
        repo: Repository name
        current_user: Authenticated user

    Returns:
        List of branches
    """
    service = GitHubService()
    branches = await service.get_repository_branches(f"{owner}/{repo}")

    return {"branches": branches}


@router.get("/repositories/{owner}/{repo}/detect")
async def detect_framework(
    owner: str,
    repo: str,
    current_user: dict = Depends(get_current_active_user)
):
    """
    Auto-detect framework and check for Dockerfile.

    Args:
        owner: Repository owner
        repo: Repository name
        current_user: Authenticated user

    Returns:
        Framework info and Dockerfile presence
    """
    service = GitHubService()
    result = await service.detect_framework(f"{owner}/{repo}")

    return result


@router.get("/repositories/{owner}/{repo}/commit")
async def get_latest_commit(
    owner: str,
    repo: str,
    branch: str = Query("main", description="Branch name"),
    current_user: dict = Depends(get_current_active_user)
):
    """
    Get latest commit SHA for a branch.

    Args:
        owner: Repository owner
        repo: Repository name
        branch: Branch name (default: main)
        current_user: Authenticated user

    Returns:
        Latest commit SHA
    """
    service = GitHubService()
    commit_sha = await service.get_latest_commit_sha(f"{owner}/{repo}", branch)

    return {"commit_sha": commit_sha}
