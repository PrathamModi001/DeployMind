"""Tests for GitHub webhooks."""
import pytest
import json
import hmac
import hashlib
from fastapi.testclient import TestClient

from api.main import app
from api.models.user import User
from api.services.database import get_db
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


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


def generate_signature(payload: str, secret: str = "") -> str:
    """Generate GitHub webhook signature."""
    if not secret:
        return ""

    signature = hmac.new(
        secret.encode(),
        payload.encode(),
        hashlib.sha256
    ).hexdigest()

    return f"sha256={signature}"


class TestWebhooks:
    """Test GitHub webhook endpoints."""

    def test_ping_event(self):
        """Test GitHub ping event."""
        payload = {"zen": "Design for failure."}

        response = client.post(
            "/api/webhooks/github",
            json=payload,
            headers={"X-GitHub-Event": "ping"}
        )

        assert response.status_code == 200
        assert "Webhook configured successfully" in response.json()["message"]

    def test_push_event_main_branch(self):
        """Test push event to main branch."""
        payload = {
            "ref": "refs/heads/main",
            "after": "abc123def456",
            "repository": {
                "full_name": "user/test-repo"
            }
        }

        response = client.post(
            "/api/webhooks/github",
            json=payload,
            headers={"X-GitHub-Event": "push"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["auto_deploy"] == True
        assert data["repository"] == "user/test-repo"
        assert data["branch"] == "main"

    def test_push_event_feature_branch(self):
        """Test push event to feature branch (should be ignored)."""
        payload = {
            "ref": "refs/heads/feature-branch",
            "after": "abc123def456",
            "repository": {
                "full_name": "user/test-repo"
            }
        }

        response = client.post(
            "/api/webhooks/github",
            json=payload,
            headers={"X-GitHub-Event": "push"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["auto_deploy"] == False
        assert "feature-branch" in data["message"]

    def test_pull_request_opened(self):
        """Test pull request opened event."""
        payload = {
            "action": "opened",
            "number": 42,
            "repository": {
                "full_name": "user/test-repo"
            }
        }

        response = client.post(
            "/api/webhooks/github",
            json=payload,
            headers={"X-GitHub-Event": "pull_request"}
        )

        assert response.status_code == 200
        data = response.json()
        assert "Preview deployment created" in data["message"]
        assert data["pr_number"] == 42

    def test_pull_request_closed(self):
        """Test pull request closed event."""
        payload = {
            "action": "closed",
            "number": 42,
            "repository": {
                "full_name": "user/test-repo"
            }
        }

        response = client.post(
            "/api/webhooks/github",
            json=payload,
            headers={"X-GitHub-Event": "pull_request"}
        )

        assert response.status_code == 200
        data = response.json()
        assert "Preview deployment removed" in data["message"]

    def test_unknown_event(self):
        """Test unknown event type."""
        payload = {"test": "data"}

        response = client.post(
            "/api/webhooks/github",
            json=payload,
            headers={"X-GitHub-Event": "unknown"}
        )

        assert response.status_code == 200
        assert "not processed" in response.json()["message"]

    def test_webhook_setup_info(self):
        """Test getting webhook setup information."""
        response = client.get("/api/webhooks/github/setup")

        assert response.status_code == 200
        data = response.json()
        assert "webhook_url" in data
        assert "content_type" in data
        assert "events" in data
        assert "instructions" in data
        assert isinstance(data["instructions"], list)
        assert len(data["instructions"]) > 0
