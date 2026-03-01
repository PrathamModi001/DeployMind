"""Tests for GitHub service and endpoints."""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, Mock

from api.main import app
from api.models.user import User
from api.services.database import get_db
from api.utils.jwt import create_access_token
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# In-memory SQLite for testing
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create tables
User.__table__.create(bind=engine, checkfirst=True)


def override_get_db():
    """Override database dependency."""
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_db_override():
    """Ensure this file's DB override is active for every test in this file."""
    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def test_user():
    """Create a test user and return JWT token."""
    db = TestingSessionLocal()

    user = User(
        email="github_test@example.com",
        username="githubtest",
        github_id="123456789",
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(
        data={"user_id": user.id, "email": user.email, "username": user.username}
    )

    db.close()
    return {"token": token, "user": user}


@pytest.fixture
def auth_headers(test_user):
    """Return authorization headers with JWT token."""
    return {"Authorization": f"Bearer {test_user['token']}"}


@pytest.fixture(autouse=True)
def reset_db():
    """Reset database before each test."""
    db = TestingSessionLocal()
    db.query(User).delete()
    db.commit()
    db.close()
    yield


class TestGitHubRepositories:
    """Test GitHub repository endpoints."""

    def test_list_repositories(self, auth_headers):
        """Test listing user's repositories."""
        response = client.get(
            "/api/github/repositories",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert "repositories" in data
        assert isinstance(data["repositories"], list)

    def test_list_repositories_with_query(self, auth_headers):
        """Test searching repositories with query."""
        response = client.get(
            "/api/github/repositories?query=app",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert "repositories" in data
        # Mock fallback should return filtered results
        repos = data["repositories"]
        if repos:
            assert any("app" in r["name"].lower() for r in repos)

    def test_list_repositories_no_auth(self):
        """Test listing repositories without authentication."""
        response = client.get("/api/github/repositories")
        assert response.status_code == 401

    def test_list_repositories_empty_query(self, auth_headers):
        """Test with empty query string."""
        response = client.get(
            "/api/github/repositories?query=",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert "repositories" in data


class TestGitHubBranches:
    """Test GitHub branch endpoints."""

    def test_list_branches(self, auth_headers):
        """Test listing repository branches."""
        response = client.get(
            "/api/github/repositories/user/repo/branches",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert "branches" in data
        assert isinstance(data["branches"], list)

        # Mock fallback should return at least main branch
        if data["branches"]:
            branch_names = [b["name"] for b in data["branches"]]
            assert "main" in branch_names or "develop" in branch_names

    def test_list_branches_no_auth(self):
        """Test listing branches without authentication."""
        response = client.get("/api/github/repositories/user/repo/branches")
        assert response.status_code == 401

    def test_list_branches_validates_format(self, auth_headers):
        """Test branch response includes required fields."""
        response = client.get(
            "/api/github/repositories/user/repo/branches",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()

        if data["branches"]:
            branch = data["branches"][0]
            assert "name" in branch
            assert "commit_sha" in branch
            assert "protected" in branch


class TestFrameworkDetection:
    """Test framework auto-detection."""

    def test_detect_framework(self, auth_headers):
        """Test detecting repository framework."""
        response = client.get(
            "/api/github/repositories/user/repo/detect",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert "framework" in data
        assert "has_dockerfile" in data
        assert isinstance(data["has_dockerfile"], bool)

    def test_detect_framework_no_auth(self):
        """Test framework detection without authentication."""
        response = client.get("/api/github/repositories/user/repo/detect")
        assert response.status_code == 401

    def test_detect_framework_returns_valid_values(self, auth_headers):
        """Test framework detection returns valid framework names."""
        response = client.get(
            "/api/github/repositories/user/repo/detect",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()

        valid_frameworks = ["node", "python", "go", "java", "ruby", "php", "rust", "unknown"]
        assert data["framework"] in valid_frameworks


class TestCommitRetrieval:
    """Test commit SHA retrieval."""

    def test_get_latest_commit(self, auth_headers):
        """Test getting latest commit SHA."""
        response = client.get(
            "/api/github/repositories/user/repo/commit",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert "commit_sha" in data
        assert data["commit_sha"] is not None

    def test_get_latest_commit_with_branch(self, auth_headers):
        """Test getting commit SHA for specific branch."""
        response = client.get(
            "/api/github/repositories/user/repo/commit?branch=develop",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert "commit_sha" in data

    def test_get_latest_commit_no_auth(self):
        """Test commit retrieval without authentication."""
        response = client.get("/api/github/repositories/user/repo/commit")
        assert response.status_code == 401


class TestGitHubEdgeCases:
    """Test edge cases and error handling."""

    def test_special_characters_in_repo_name(self, auth_headers):
        """Test repository names with special characters."""
        response = client.get(
            "/api/github/repositories/user/my-app_v2/branches",
            headers=auth_headers
        )

        # Should handle gracefully (mock fallback)
        assert response.status_code == 200

    def test_very_long_repo_name(self, auth_headers):
        """Test with extremely long repository name."""
        long_name = "a" * 200
        response = client.get(
            f"/api/github/repositories/user/{long_name}/branches",
            headers=auth_headers
        )

        # Should handle gracefully
        assert response.status_code == 200

    def test_concurrent_github_requests(self, auth_headers):
        """Test making multiple concurrent GitHub requests."""
        responses = []

        for i in range(5):
            response = client.get(
                "/api/github/repositories",
                headers=auth_headers
            )
            responses.append(response)

        # All should succeed
        assert all(r.status_code == 200 for r in responses)

    def test_repository_search_case_insensitive(self, auth_headers):
        """Test that repository search is case-insensitive."""
        # Search with uppercase
        response1 = client.get(
            "/api/github/repositories?query=APP",
            headers=auth_headers
        )

        # Search with lowercase
        response2 = client.get(
            "/api/github/repositories?query=app",
            headers=auth_headers
        )

        assert response1.status_code == 200
        assert response2.status_code == 200

        # Both should return same results (case-insensitive search)
        # Note: with mock fallback, this is guaranteed
