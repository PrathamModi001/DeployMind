"""Tests for monitoring endpoints."""
import pytest
from fastapi.testclient import TestClient

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


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


@pytest.fixture
def test_user():
    """Create a test user and return JWT token."""
    db = TestingSessionLocal()

    user = User(
        email="monitor_test@example.com",
        username="monitortest",
        github_id="77777777",
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


class TestMonitoring:
    """Test monitoring endpoints."""

    def test_get_metrics(self, auth_headers):
        """Test getting deployment metrics."""
        response = client.get(
            "/api/monitoring/deployments/deploy-123/metrics",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert "deployment_id" in data
        assert "metrics" in data
        assert "timestamp" in data

        metrics = data["metrics"]
        assert "cpu_utilization" in metrics
        assert "memory_used_mb" in metrics
        assert "memory_total_mb" in metrics
        assert "network_in_mb" in metrics
        assert "network_out_mb" in metrics
        assert "disk_used_gb" in metrics
        assert "disk_total_gb" in metrics
        assert "memory_used_percent" in metrics
        assert "disk_used_percent" in metrics

    def test_get_metrics_history(self, auth_headers):
        """Test getting metrics history."""
        response = client.get(
            "/api/monitoring/deployments/deploy-123/metrics/history?hours=2",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert "deployment_id" in data
        assert "hours" in data
        assert "interval_minutes" in data
        assert "data" in data
        assert isinstance(data["data"], list)
        assert len(data["data"]) > 0

        # Check data point structure
        point = data["data"][0]
        assert "timestamp" in point
        assert "cpu_utilization" in point
        assert "memory_used_mb" in point
        assert "network_in_mb" in point
        assert "network_out_mb" in point

    def test_get_metrics_history_invalid_hours(self, auth_headers):
        """Test metrics history with invalid hours."""
        response = client.get(
            "/api/monitoring/deployments/deploy-123/metrics/history?hours=25",
            headers=auth_headers
        )

        assert response.status_code == 400
        assert "between 1 and 24" in response.json()["detail"]

    def test_get_health(self, auth_headers):
        """Test getting deployment health."""
        response = client.get(
            "/api/monitoring/deployments/deploy-123/health",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert "deployment_id" in data
        assert "status" in data
        assert "status_color" in data
        assert "issues" in data
        assert "last_check" in data
        assert "uptime_seconds" in data
        assert "http_status" in data
        assert "response_time_ms" in data

        assert data["status"] in ["healthy", "warning", "critical"]
        assert isinstance(data["issues"], list)

    def test_monitoring_no_auth(self):
        """Test monitoring endpoints without authentication."""
        response = client.get("/api/monitoring/deployments/deploy-123/metrics")
        assert response.status_code == 401

        response = client.get("/api/monitoring/deployments/deploy-123/metrics/history")
        assert response.status_code == 401

        response = client.get("/api/monitoring/deployments/deploy-123/health")
        assert response.status_code == 401
