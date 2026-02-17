"""API endpoint tests."""
import pytest
from fastapi.testclient import TestClient
from api.main import app

client = TestClient(app)


class TestHealthEndpoints:
    """Test health check endpoints."""

    def test_root_endpoint(self):
        """Test root endpoint returns API info."""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "name" in data
        assert "version" in data
        assert data["name"] == "DeployMind API"

    def test_health_endpoint(self):
        """Test health check endpoint."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "deploymind-api"

    def test_api_health_endpoint(self):
        """Test API health endpoint."""
        response = client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"


class TestAuthEndpoints:
    """Test authentication endpoints."""

    def test_register_new_user(self):
        """Test user registration."""
        response = client.post(
            "/api/auth/register",
            json={
                "email": "test@example.com",
                "username": "testuser",
                "password": "testpass123",
                "full_name": "Test User"
            }
        )
        assert response.status_code == 201
        data = response.json()
        assert data["email"] == "test@example.com"
        assert data["username"] == "testuser"
        assert "id" in data
        assert "hashed_password" not in data  # Should not expose password

    def test_login_success(self):
        """Test successful login."""
        response = client.post(
            "/api/auth/login",
            json={
                "email": "admin@deploymind.io",
                "password": "admin123"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    def test_login_invalid_credentials(self):
        """Test login with invalid credentials."""
        response = client.post(
            "/api/auth/login",
            json={
                "email": "admin@deploymind.io",
                "password": "wrongpassword"
            }
        )
        assert response.status_code == 401
        assert "detail" in response.json()

    def test_get_current_user_without_token(self):
        """Test accessing protected endpoint without token."""
        response = client.get("/api/auth/me")
        assert response.status_code == 401

    def test_get_current_user_with_token(self):
        """Test accessing protected endpoint with valid token."""
        # First login
        login_response = client.post(
            "/api/auth/login",
            json={
                "email": "admin@deploymind.io",
                "password": "admin123"
            }
        )
        token = login_response.json()["access_token"]

        # Then access protected endpoint
        response = client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "admin@deploymind.io"


class TestDeploymentEndpoints:
    """Test deployment endpoints."""

    @pytest.fixture
    def auth_token(self):
        """Get authentication token for tests."""
        response = client.post(
            "/api/auth/login",
            json={
                "email": "admin@deploymind.io",
                "password": "admin123"
            }
        )
        return response.json()["access_token"]

    def test_list_deployments(self, auth_token):
        """Test listing deployments."""
        response = client.get(
            "/api/deployments",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "deployments" in data
        assert "total" in data
        assert "page" in data

    def test_get_deployment(self, auth_token):
        """Test getting specific deployment."""
        response = client.get(
            "/api/deployments/a8083a12",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "a8083a12"
        assert "repository" in data
        assert "status" in data

    def test_get_nonexistent_deployment(self, auth_token):
        """Test getting non-existent deployment."""
        response = client.get(
            "/api/deployments/nonexistent",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 404

    def test_create_deployment(self, auth_token):
        """Test creating new deployment."""
        response = client.post(
            "/api/deployments",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={
                "repository": "owner/repo",
                "instance_id": "i-1234567890abcdef0",
                "port": 8080,
                "strategy": "rolling",
                "environment": "production"
            }
        )
        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert data["repository"] == "owner/repo"
        assert data["status"] == "PENDING"


class TestAnalyticsEndpoints:
    """Test analytics endpoints."""

    @pytest.fixture
    def auth_token(self):
        """Get authentication token for tests."""
        response = client.post(
            "/api/auth/login",
            json={
                "email": "admin@deploymind.io",
                "password": "admin123"
            }
        )
        return response.json()["access_token"]

    def test_get_analytics_overview(self, auth_token):
        """Test analytics overview."""
        response = client.get(
            "/api/analytics/overview",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "total_deployments" in data
        assert "success_rate" in data
        assert "average_duration_seconds" in data

    def test_get_deployment_timeline(self, auth_token):
        """Test deployment timeline."""
        response = client.get(
            "/api/analytics/timeline?days=7",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "timeline" in data
        assert len(data["timeline"]) == 7

    def test_get_performance_metrics(self, auth_token):
        """Test performance metrics."""
        response = client.get(
            "/api/analytics/performance",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "build_times_by_language" in data
        assert "deployment_times_by_strategy" in data
        assert "health_check_response_times" in data


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
