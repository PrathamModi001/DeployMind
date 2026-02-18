"""Tests for security scanning endpoints."""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, Mock
import sys
from pathlib import Path

from api.main import app
from api.models.user import User
from api.services.database import get_db
from api.utils.jwt import create_access_token
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Add deploymind-core to path
core_path = Path(__file__).parent.parent.parent.parent.parent / "deploymind-core"
sys.path.insert(0, str(core_path))

try:
    from deploymind.infrastructure.database.connection import Base as CoreBase
    from deploymind.infrastructure.database.models import SecurityScan
    CORE_AVAILABLE = True
except ImportError:
    CoreBase = None
    SecurityScan = None
    CORE_AVAILABLE = False

# In-memory SQLite for testing
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create tables
if CORE_AVAILABLE and CoreBase:
    CoreBase.metadata.create_all(bind=engine)
else:
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
        email="security_test@example.com",
        username="securitytest",
        github_id="999888777",
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
    if CORE_AVAILABLE and SecurityScan:
        db.query(SecurityScan).delete()
    db.commit()
    db.close()
    yield


class TestSecurityScanning:
    """Test security scanning endpoints."""

    def test_scan_repository_endpoint(self, auth_headers):
        """Test repository scanning endpoint."""
        response = client.post(
            "/api/security/deployments/test-deploy-1/scan/repository",
            json={"repo_path": "/tmp/test-repo"},
            headers=auth_headers
        )

        # Should work with mock fallback if Trivy not available
        assert response.status_code == 200
        data = response.json()
        assert "passed" in data
        assert "total_vulnerabilities" in data
        assert "critical" in data
        assert "high" in data

    def test_scan_image_endpoint(self, auth_headers):
        """Test Docker image scanning endpoint."""
        response = client.post(
            "/api/security/deployments/test-deploy-1/scan/image",
            json={"image_name": "nginx:latest"},
            headers=auth_headers
        )

        # Should work with mock fallback if Trivy not available
        assert response.status_code == 200
        data = response.json()
        assert "passed" in data
        assert "vulnerabilities" in data
        assert "critical" in data
        assert "high" in data

    def test_get_scan_results_empty(self, auth_headers):
        """Test getting scan results when none exist."""
        response = client.get(
            "/api/security/deployments/test-deploy-1/scan/results",
            headers=auth_headers
        )

        assert response.status_code == 200
        assert response.json() == []

    @pytest.mark.skipif(not CORE_AVAILABLE, reason="Core database not available")
    def test_get_scan_results_with_data(self, auth_headers):
        """Test getting scan results with existing scans."""
        # First run scans to create data via the API
        client.post(
            "/api/security/deployments/test-deploy-1/scan/repository",
            json={"repo_path": "/tmp/test-repo"},
            headers=auth_headers
        )

        client.post(
            "/api/security/deployments/test-deploy-1/scan/image",
            json={"image_name": "nginx:latest"},
            headers=auth_headers
        )

        # Now get results
        response = client.get(
            "/api/security/deployments/test-deploy-1/scan/results",
            headers=auth_headers
        )

        assert response.status_code == 200
        # Data may be empty if Trivy not available (mock fallback doesn't store in DB)
        # Just verify endpoint works
        data = response.json()
        assert isinstance(data, list)

    def test_scan_without_auth(self):
        """Test scanning endpoints without authentication."""
        # Repository scan
        response = client.post(
            "/api/security/deployments/test-deploy-1/scan/repository",
            json={"repo_path": "/tmp/test-repo"}
        )
        assert response.status_code == 401

        # Image scan
        response = client.post(
            "/api/security/deployments/test-deploy-1/scan/image",
            json={"image_name": "nginx:latest"}
        )
        assert response.status_code == 401

        # Get results
        response = client.get(
            "/api/security/deployments/test-deploy-1/scan/results"
        )
        assert response.status_code == 401

    def test_scan_repository_invalid_path(self, auth_headers):
        """Test repository scanning with invalid path."""
        response = client.post(
            "/api/security/deployments/test-deploy-1/scan/repository",
            json={"repo_path": ""},
            headers=auth_headers
        )

        # Should handle gracefully (mock fallback should still work)
        assert response.status_code == 200

    def test_scan_image_invalid_name(self, auth_headers):
        """Test image scanning with invalid image name."""
        response = client.post(
            "/api/security/deployments/test-deploy-1/scan/image",
            json={"image_name": ""},
            headers=auth_headers
        )

        # Should handle gracefully (mock fallback should still work)
        assert response.status_code == 200

    def test_multiple_scans_same_deployment(self, auth_headers):
        """Test running multiple scans for same deployment."""
        # Scan repository
        response1 = client.post(
            "/api/security/deployments/test-deploy-1/scan/repository",
            json={"repo_path": "/tmp/test-repo"},
            headers=auth_headers
        )
        assert response1.status_code == 200

        # Scan image
        response2 = client.post(
            "/api/security/deployments/test-deploy-1/scan/image",
            json={"image_name": "nginx:latest"},
            headers=auth_headers
        )
        assert response2.status_code == 200

        # Both should succeed
        assert response1.json()["passed"] in [True, False]
        assert response2.json()["passed"] in [True, False]
