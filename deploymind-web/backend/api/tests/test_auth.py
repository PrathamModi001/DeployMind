"""Tests for authentication endpoints (GitHub OAuth only).

Run with: pytest api/tests/test_auth.py -v
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from unittest.mock import patch, Mock

from api.main import app
from api.services.database import get_db
from api.models.user import User

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


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_db():
    """Reset database before each test."""
    db = TestingSessionLocal()
    db.query(User).delete()
    db.commit()
    db.close()
    yield


class TestGitHubOAuth:
    """Test GitHub OAuth endpoints."""

    def test_get_github_oauth_url(self):
        """Test getting GitHub OAuth URL."""
        response = client.get("/api/auth/github")

        assert response.status_code == 200
        data = response.json()
        assert "url" in data
        assert "github.com/login/oauth/authorize" in data["url"]
        assert "client_id" in data


class TestCurrentUser:
    """Test get current user endpoint."""

    def test_get_current_user_no_token(self):
        """Test getting current user without token."""
        response = client.get("/api/auth/me")
        assert response.status_code == 401

    def test_get_current_user_invalid_token(self):
        """Test getting current user with invalid token."""
        response = client.get(
            "/api/auth/me",
            headers={"Authorization": "Bearer invalid_token"}
        )
        assert response.status_code == 401


class TestLogout:
    """Test logout endpoint."""

    def test_logout_no_token(self):
        """Test logout without token."""
        response = client.post("/api/auth/logout")
        assert response.status_code == 401
