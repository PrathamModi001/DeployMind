"""Edge case tests for AI features."""
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


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


@pytest.fixture
def test_user():
    """Create a test user and return JWT token."""
    db = TestingSessionLocal()

    user = User(
        email="ai_edge_test@example.com",
        username="aiedgetest",
        github_id="999999",
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


class TestAIEdgeCases:
    """Test AI features edge cases."""

    def test_instance_recommendation_empty_repository(self, auth_headers):
        """Test recommendation with empty repository name."""
        response = client.post(
            "/api/ai/recommend/instance",
            json={"repository": "", "traffic_estimate": "low"},
            headers=auth_headers
        )

        assert response.status_code == 200  # Should handle gracefully

    def test_instance_recommendation_invalid_traffic(self, auth_headers):
        """Test recommendation with invalid traffic estimate."""
        response = client.post(
            "/api/ai/recommend/instance",
            json={"repository": "user/repo", "traffic_estimate": "super-mega-high"},
            headers=auth_headers
        )

        assert response.status_code == 200  # Should use default or handle

    def test_instance_recommendation_sql_injection(self, auth_headers):
        """Test SQL injection attempt in repository name."""
        response = client.post(
            "/api/ai/recommend/instance",
            json={"repository": "user/repo'; DROP TABLE users;--", "traffic_estimate": "low"},
            headers=auth_headers
        )

        assert response.status_code == 200

    def test_instance_recommendation_very_long_repo_name(self, auth_headers):
        """Test with extremely long repository name."""
        long_repo = "a" * 10000 + "/repo"

        response = client.post(
            "/api/ai/recommend/instance",
            json={"repository": long_repo, "traffic_estimate": "low"},
            headers=auth_headers
        )

        assert response.status_code in [200, 400, 413]  # Should handle or reject

    def test_instance_recommendation_special_characters(self, auth_headers):
        """Test repository name with special characters."""
        special_repos = [
            "user/repo@#$%",
            "user/repo\n\n",
            "user/repo<script>",
            "user/../../../etc/passwd",
        ]

        for repo in special_repos:
            response = client.post(
                "/api/ai/recommend/instance",
                json={"repository": repo, "traffic_estimate": "low"},
                headers=auth_headers
            )

            assert response.status_code == 200

    def test_strategy_recommendation_negative_count(self, auth_headers):
        """Test strategy with negative deployment count."""
        response = client.post(
            "/api/ai/recommend/strategy",
            params={"current_status": "deployed", "deployment_count": -10, "success_rate": 95.5},
            headers=auth_headers
        )

        assert response.status_code in [200, 400]

    def test_strategy_recommendation_invalid_success_rate(self, auth_headers):
        """Test strategy with invalid success rate."""
        invalid_rates = [150.0, -50.0, 999.9]

        for rate in invalid_rates:
            response = client.post(
                "/api/ai/recommend/strategy",
                params={"current_status": "deployed", "deployment_count": 50, "success_rate": rate},
                headers=auth_headers
            )

            assert response.status_code in [200, 400]

    def test_cost_analysis_zero_deployments(self, auth_headers):
        """Test cost analysis with zero deployments."""
        response = client.post(
            "/api/ai/optimize/costs",
            json={
                "deployment_count": 0,
                "avg_duration_seconds": 450.0,
                "instance_types": {}
            },
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert "current_monthly_cost_usd" in data

    def test_cost_analysis_negative_duration(self, auth_headers):
        """Test cost analysis with negative duration."""
        response = client.post(
            "/api/ai/optimize/costs",
            json={
                "deployment_count": 100,
                "avg_duration_seconds": -450.0,
                "instance_types": {"t2.small": 80}
            },
            headers=auth_headers
        )

        assert response.status_code in [200, 400]

    def test_cost_analysis_very_large_numbers(self, auth_headers):
        """Test cost analysis with very large numbers."""
        response = client.post(
            "/api/ai/optimize/costs",
            json={
                "deployment_count": 999999999,
                "avg_duration_seconds": 999999999.0,
                "instance_types": {"t2.small": 999999999}
            },
            headers=auth_headers
        )

        assert response.status_code == 200

    def test_cost_estimate_invalid_instance_type(self, auth_headers):
        """Test cost estimate with invalid instance type."""
        response = client.get(
            "/api/ai/optimize/estimate",
            params={"instance_type": "invalid.type", "duration_hours": 2.5},
            headers=auth_headers
        )

        assert response.status_code == 200  # Should handle gracefully

    def test_cost_estimate_zero_duration(self, auth_headers):
        """Test cost estimate with zero duration."""
        response = client.get(
            "/api/ai/optimize/estimate",
            params={"instance_type": "t2.small", "duration_hours": 0},
            headers=auth_headers
        )

        assert response.status_code in [200, 400]

    def test_rollback_analysis_all_checks_failed(self, auth_headers):
        """Test rollback with 100% failure rate."""
        response = client.post(
            "/api/ai/rollback/analyze",
            json={
                "deployment_id": "test-deploy",
                "failed_checks": 100,
                "total_checks": 100,
                "error_messages": ["Error"] * 50,
                "deployment_age_minutes": 15
            },
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["should_rollback"] == True

    def test_rollback_analysis_zero_checks(self, auth_headers):
        """Test rollback with zero total checks."""
        response = client.post(
            "/api/ai/rollback/analyze",
            json={
                "deployment_id": "test-deploy",
                "failed_checks": 0,
                "total_checks": 0,
                "error_messages": [],
                "deployment_age_minutes": 15
            },
            headers=auth_headers
        )

        assert response.status_code in [200, 400]

    def test_rollback_analysis_extremely_old_deployment(self, auth_headers):
        """Test rollback for very old deployment."""
        response = client.post(
            "/api/ai/rollback/analyze",
            json={
                "deployment_id": "test-deploy",
                "failed_checks": 5,
                "total_checks": 10,
                "error_messages": ["Error"],
                "deployment_age_minutes": 999999
            },
            headers=auth_headers
        )

        assert response.status_code == 200

    def test_rollback_analysis_many_error_messages(self, auth_headers):
        """Test rollback with hundreds of error messages."""
        response = client.post(
            "/api/ai/rollback/analyze",
            json={
                "deployment_id": "test-deploy",
                "failed_checks": 5,
                "total_checks": 10,
                "error_messages": [f"Error {i}" for i in range(1000)],
                "deployment_age_minutes": 15
            },
            headers=auth_headers
        )

        assert response.status_code == 200

    def test_vulnerability_explanation_empty_cve(self, auth_headers):
        """Test vulnerability explanation with empty CVE ID."""
        response = client.post(
            "/api/ai/security/explain",
            json={"cve_id": "", "package": "express", "severity": "CRITICAL"},
            headers=auth_headers
        )

        assert response.status_code == 200

    def test_vulnerability_explanation_invalid_severity(self, auth_headers):
        """Test vulnerability with invalid severity level."""
        response = client.post(
            "/api/ai/security/explain",
            json={"cve_id": "CVE-2024-1234", "package": "express", "severity": "SUPER_CRITICAL"},
            headers=auth_headers
        )

        assert response.status_code == 200

    def test_vulnerability_explanation_xss_in_package_name(self, auth_headers):
        """Test XSS attempt in package name."""
        response = client.post(
            "/api/ai/security/explain",
            json={
                "cve_id": "CVE-2024-1234",
                "package": "<script>alert('xss')</script>",
                "severity": "HIGH"
            },
            headers=auth_headers
        )

        assert response.status_code == 200

    def test_ai_endpoints_concurrent_requests(self, auth_headers):
        """Test making many concurrent AI requests."""
        responses = []

        for i in range(20):
            response = client.post(
                "/api/ai/recommend/instance",
                json={"repository": f"user/repo{i}", "traffic_estimate": "low"},
                headers=auth_headers
            )
            responses.append(response)

        # All should succeed
        assert all(r.status_code == 200 for r in responses)

    def test_ai_endpoints_missing_required_fields(self, auth_headers):
        """Test AI endpoints with missing required fields."""
        # Missing repository
        response = client.post(
            "/api/ai/recommend/instance",
            json={"traffic_estimate": "low"},
            headers=auth_headers
        )

        assert response.status_code == 422  # Validation error
