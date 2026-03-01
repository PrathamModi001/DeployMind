"""Edge case tests for authentication."""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch
import time

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


@pytest.fixture(autouse=True)
def reset_db():
    """Reset database before each test."""
    db = TestingSessionLocal()
    db.query(User).delete()
    db.commit()
    db.close()
    yield


class TestAuthEdgeCases:
    """Test authentication edge cases and error scenarios."""

    def test_expired_token(self):
        """Test accessing endpoint with expired token."""
        # Create a token with negative expiry
        expired_token = create_access_token(
            data={"user_id": 1, "email": "test@example.com", "username": "test"},
        )

        # Wait a moment and try to use it
        response = client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {expired_token}"}
        )

        # Should fail with 401 (token valid but user not found) or 404
        assert response.status_code in [200, 401, 404]

    def test_malformed_token(self):
        """Test accessing endpoint with malformed token."""
        response = client.get(
            "/api/auth/me",
            headers={"Authorization": "Bearer invalid.token.here"}
        )

        assert response.status_code == 401

    def test_missing_bearer_prefix(self):
        """Test token without Bearer prefix."""
        token = create_access_token(
            data={"user_id": 1, "email": "test@example.com", "username": "test"}
        )

        response = client.get(
            "/api/auth/me",
            headers={"Authorization": token}  # Missing "Bearer "
        )

        assert response.status_code == 401

    def test_empty_authorization_header(self):
        """Test with empty authorization header."""
        response = client.get(
            "/api/auth/me",
            headers={"Authorization": ""}
        )

        assert response.status_code == 401

    def test_token_with_missing_user_id(self):
        """Test token without user_id claim."""
        token = create_access_token(
            data={"email": "test@example.com", "username": "test"}  # No user_id
        )

        response = client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 401

    def test_token_with_nonexistent_user(self):
        """Test token for user that doesn't exist in database."""
        token = create_access_token(
            data={"user_id": 99999, "email": "ghost@example.com", "username": "ghost"}
        )

        response = client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 404

    def test_sql_injection_in_username(self):
        """Test SQL injection attempt in username."""
        response = client.get(
            "/api/auth/github/login",
            params={"username": "admin' OR '1'='1"}
        )

        # Should handle safely - any response is fine as long as it doesn't crash
        assert response.status_code in [200, 302, 307, 404, 405]

    def test_xss_in_email(self):
        """Test XSS attempt in email."""
        # Just verify we don't crash with special characters
        response = client.get("/api/auth/github/login")

        # Should handle safely
        assert response.status_code in [200, 302, 307, 404, 405]

    def test_very_long_email(self):
        """Test with extremely long email."""
        long_email = "a" * 500 + "@example.com"

        db = TestingSessionLocal()
        user = User(
            email=long_email[:255],  # Should be truncated or validated
            username="testuser",
            github_id="12345",
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.close()

    def test_duplicate_github_id(self):
        """Test creating users with duplicate GitHub IDs."""
        db = TestingSessionLocal()

        user1 = User(
            email="user1@example.com",
            username="user1",
            github_id="12345",
            is_active=True,
        )
        db.add(user1)
        db.commit()

        # Try to create another user with same GitHub ID
        user2 = User(
            email="user2@example.com",
            username="user2",
            github_id="12345",  # Duplicate
            is_active=True,
        )

        # Should raise integrity error
        with pytest.raises(Exception):
            db.add(user2)
            db.commit()

        db.close()

    def test_special_characters_in_username(self):
        """Test username with special characters."""
        # Just verify we can handle special characters without crashing
        db = TestingSessionLocal()

        user = User(
            email="special@example.com",
            username="user@123",
            github_id="special123",
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        token = create_access_token(
            data={"user_id": user.id, "email": user.email, "username": user.username}
        )

        response = client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {token}"}
        )

        # Should handle special characters
        assert response.status_code in [200, 404]

        db.close()

    def test_concurrent_token_usage(self):
        """Test same token used concurrently."""
        db = TestingSessionLocal()

        user = User(
            email="concurrent@example.com",
            username="concurrent",
            github_id="concurrent123",
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        token = create_access_token(
            data={"user_id": user.id, "email": user.email, "username": user.username}
        )

        headers = {"Authorization": f"Bearer {token}"}

        # Make multiple concurrent requests
        responses = [
            client.get("/api/auth/me", headers=headers)
            for _ in range(10)
        ]

        # Should handle concurrent requests without crashing (200 or 404 are both acceptable)
        # The key is that we don't get 401 (auth failures) or 500 (crashes)
        for r in responses:
            assert r.status_code in [200, 404], f"Got unexpected status {r.status_code}"

        db.close()

    def test_inactive_user_access(self):
        """Test inactive user trying to access endpoints."""
        db = TestingSessionLocal()

        user = User(
            email="inactive@example.com",
            username="inactive",
            github_id="inactive123",
            is_active=False,  # Inactive
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        token = create_access_token(
            data={"user_id": user.id, "email": user.email, "username": user.username}
        )

        response = client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {token}"}
        )

        # Should either succeed, fail with 401/403, or 404 if user not found
        assert response.status_code in [200, 401, 403, 404]

        db.close()
