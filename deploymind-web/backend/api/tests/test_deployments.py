"""Tests for deployment endpoints.

Run with: pytest api/tests/test_deployments.py -v
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from unittest.mock import patch, Mock
import sys
from pathlib import Path

from api.main import app
from api.services.database import get_db
from api.models.user import User
from api.utils.jwt import create_access_token

# Add deploymind-core to path
core_path = Path(__file__).parent.parent.parent.parent / "deploymind-core"
sys.path.insert(0, str(core_path))

try:
    from deploymind.infrastructure.database.models import (
        Deployment,
        DeploymentLog,
        DeploymentStatusEnum,
        DeploymentStrategyEnum,
    )
    from deploymind.infrastructure.database.connection import Base as CoreBase
    CORE_AVAILABLE = True
except ImportError:
    # Mock if core not available
    Deployment = None
    DeploymentLog = None
    DeploymentStatusEnum = None
    DeploymentStrategyEnum = None
    CoreBase = None
    CORE_AVAILABLE = False

# In-memory SQLite for testing
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create all tables from deploymind-core and web
if CORE_AVAILABLE and CoreBase:
    # Create all core tables (Deployment, DeploymentLog, etc.)
    CoreBase.metadata.create_all(bind=engine)
else:
    # Fallback: create individual tables
    User.__table__.create(bind=engine, checkfirst=True)
    if Deployment:
        Deployment.__table__.create(bind=engine, checkfirst=True)
    if DeploymentLog:
        DeploymentLog.__table__.create(bind=engine, checkfirst=True)


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

    # Create user (GitHub OAuth)
    user = User(
        email="test@example.com",
        username="testuser",
        github_id="12345678",  # Required for GitHub OAuth
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # Create JWT token
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
    if Deployment:
        db.query(Deployment).delete()
    if DeploymentLog:
        db.query(DeploymentLog).delete()
    db.query(User).delete()
    db.commit()
    db.close()
    yield


@pytest.mark.skipif(not Deployment, reason="Deployment model not available")
class TestDeploymentsList:
    """Test deployment list endpoint."""

    def test_list_deployments_empty(self, auth_headers):
        """Test listing deployments when database is empty."""
        response = client.get("/api/deployments", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["page"] == 1
        assert data["page_size"] == 10
        assert data["deployments"] == []

    def test_list_deployments_with_data(self, auth_headers):
        """Test listing deployments with existing data."""
        db = TestingSessionLocal()

        # Create test deployment
        deployment = Deployment(
            id="test-deploy-1",
            repository="owner/repo",
            instance_id="i-0123456789abcdef0",
            status=DeploymentStatusEnum.DEPLOYED,
            strategy=DeploymentStrategyEnum.ROLLING,
            extra_data={"port": 8080, "environment": "production"},
        )
        db.add(deployment)
        db.commit()
        db.close()

        response = client.get("/api/deployments", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert len(data["deployments"]) == 1
        assert data["deployments"][0]["id"] == "test-deploy-1"
        assert data["deployments"][0]["repository"] == "owner/repo"

    def test_list_deployments_pagination(self, auth_headers):
        """Test deployment list pagination."""
        db = TestingSessionLocal()

        # Create 15 test deployments
        for i in range(15):
            deployment = Deployment(
                id=f"test-deploy-{i}",
                repository=f"owner/repo-{i}",
                instance_id="i-0123456789abcdef0",
                status=DeploymentStatusEnum.PENDING,
                strategy=DeploymentStrategyEnum.ROLLING,
            )
            db.add(deployment)
        db.commit()
        db.close()

        # Get first page
        response = client.get("/api/deployments?page=1&page_size=10", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 15
        assert len(data["deployments"]) == 10

        # Get second page
        response = client.get("/api/deployments?page=2&page_size=10", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 15
        assert len(data["deployments"]) == 5

    def test_list_deployments_filter_by_status(self, auth_headers):
        """Test filtering deployments by status."""
        db = TestingSessionLocal()

        # Create deployments with different statuses
        deployment1 = Deployment(
            id="deploy-1",
            repository="owner/repo1",
            instance_id="i-0123456789abcdef0",
            status=DeploymentStatusEnum.DEPLOYED,
            strategy=DeploymentStrategyEnum.ROLLING,
        )
        deployment2 = Deployment(
            id="deploy-2",
            repository="owner/repo2",
            instance_id="i-0123456789abcdef0",
            status=DeploymentStatusEnum.PENDING,
            strategy=DeploymentStrategyEnum.ROLLING,
        )
        db.add(deployment1)
        db.add(deployment2)
        db.commit()
        db.close()

        # Filter by DEPLOYED status
        response = client.get("/api/deployments?status=DEPLOYED", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["deployments"][0]["status"] == "DEPLOYED"

    def test_list_deployments_no_auth(self):
        """Test listing deployments without authentication."""
        response = client.get("/api/deployments")
        assert response.status_code == 401


@pytest.mark.skipif(not Deployment, reason="Deployment model not available")
class TestGetDeployment:
    """Test get deployment by ID endpoint."""

    def test_get_deployment_success(self, auth_headers):
        """Test getting a deployment by ID."""
        db = TestingSessionLocal()

        deployment = Deployment(
            id="test-deploy-1",
            repository="owner/repo",
            instance_id="i-0123456789abcdef0",
            status=DeploymentStatusEnum.DEPLOYED,
            strategy=DeploymentStrategyEnum.ROLLING,
            commit_sha="abc123",
            image_tag="repo:abc123",
            extra_data={"port": 8080, "environment": "production"},
        )
        db.add(deployment)
        db.commit()
        db.close()

        response = client.get("/api/deployments/test-deploy-1", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "test-deploy-1"
        assert data["repository"] == "owner/repo"
        assert data["status"] == "DEPLOYED"
        assert data["commit_sha"] == "abc123"

    def test_get_deployment_not_found(self, auth_headers):
        """Test getting a non-existent deployment."""
        response = client.get("/api/deployments/nonexistent", headers=auth_headers)
        assert response.status_code == 404


@pytest.mark.skipif(not Deployment, reason="Deployment model not available")
class TestCreateDeployment:
    """Test create deployment endpoint."""

    def test_create_deployment_success(self, auth_headers):
        """Test creating a new deployment."""
        deployment_data = {
            "repository": "owner/repo",
            "instance_id": "i-0123456789abcdef0",
            "port": 8080,
            "strategy": "rolling",
            "environment": "production",
        }

        response = client.post(
            "/api/deployments",
            json=deployment_data,
            headers=auth_headers
        )

        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert data["repository"] == "owner/repo"
        assert data["status"] == "PENDING"
        assert data["port"] == 8080

    def test_create_deployment_invalid_instance_id(self, auth_headers):
        """Test creating deployment with invalid instance ID."""
        deployment_data = {
            "repository": "owner/repo",
            "instance_id": "invalid-id",  # Invalid format
            "port": 8080,
        }

        response = client.post(
            "/api/deployments",
            json=deployment_data,
            headers=auth_headers
        )

        assert response.status_code == 422  # Validation error


@pytest.mark.skipif(not Deployment or not DeploymentLog, reason="Models not available")
class TestDeploymentLogs:
    """Test deployment logs endpoint."""

    def test_get_deployment_logs_empty(self, auth_headers):
        """Test getting logs for deployment with no logs."""
        db = TestingSessionLocal()

        deployment = Deployment(
            id="test-deploy-1",
            repository="owner/repo",
            instance_id="i-0123456789abcdef0",
            status=DeploymentStatusEnum.DEPLOYED,
            strategy=DeploymentStrategyEnum.ROLLING,
        )
        db.add(deployment)
        db.commit()
        db.close()

        response = client.get("/api/deployments/test-deploy-1/logs", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["deployment_id"] == "test-deploy-1"
        assert data["logs"] == []

    def test_get_deployment_logs_with_data(self, auth_headers):
        """Test getting logs for deployment with log entries."""
        db = TestingSessionLocal()

        deployment = Deployment(
            id="test-deploy-1",
            repository="owner/repo",
            instance_id="i-0123456789abcdef0",
            status=DeploymentStatusEnum.DEPLOYED,
            strategy=DeploymentStrategyEnum.ROLLING,
        )
        db.add(deployment)

        # Add log entries
        log1 = DeploymentLog(
            deployment_id="test-deploy-1",
            level="INFO",
            message="Starting deployment",
            agent="orchestrator",
        )
        log2 = DeploymentLog(
            deployment_id="test-deploy-1",
            level="INFO",
            message="Deployment complete",
            agent="deploy",
        )
        db.add(log1)
        db.add(log2)
        db.commit()
        db.close()

        response = client.get("/api/deployments/test-deploy-1/logs", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert len(data["logs"]) == 2
        assert data["logs"][0]["message"] == "Starting deployment"
        assert data["logs"][1]["message"] == "Deployment complete"


@pytest.mark.skipif(not Deployment, reason="Deployment model not available")
class TestRollbackDeployment:
    """Test deployment rollback endpoint."""

    def test_rollback_deployment_success(self, auth_headers):
        """Test rolling back a deployment."""
        db = TestingSessionLocal()

        deployment = Deployment(
            id="test-deploy-1",
            repository="owner/repo",
            instance_id="i-0123456789abcdef0",
            status=DeploymentStatusEnum.DEPLOYED,
            strategy=DeploymentStrategyEnum.ROLLING,
        )
        db.add(deployment)
        db.commit()
        db.close()

        response = client.post(
            "/api/deployments/test-deploy-1/rollback",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "test-deploy-1"
        assert data["status"] == "ROLLED_BACK"

    def test_rollback_nonexistent_deployment(self, auth_headers):
        """Test rolling back a non-existent deployment."""
        response = client.post(
            "/api/deployments/nonexistent/rollback",
            headers=auth_headers
        )

        assert response.status_code == 404
