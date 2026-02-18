"""Tests for AI-powered features.

Run with: pytest api/tests/test_ai.py -v
"""
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
        email="ai_test@example.com",
        username="aitest",
        github_id="99999999",
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


class TestInstanceRecommendation:
    """Test AI instance recommendation endpoint."""

    def test_recommend_instance_success(self, auth_headers):
        """Test getting instance recommendation."""
        response = client.post(
            "/api/ai/recommend/instance",
            json={
                "repository": "user/test-repo",
                "language": "python",
                "traffic_estimate": "medium"
            },
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert "recommended_instance" in data
        assert "reasoning" in data
        assert "estimated_cost_monthly_usd" in data
        assert "alternatives" in data

    def test_recommend_instance_no_auth(self):
        """Test recommendation without authentication."""
        response = client.post(
            "/api/ai/recommend/instance",
            json={"repository": "user/repo", "traffic_estimate": "low"}
        )
        assert response.status_code == 401


class TestStrategyRecommendation:
    """Test AI deployment strategy recommendation."""

    def test_recommend_strategy_high_success_rate(self, auth_headers):
        """Test strategy recommendation with high success rate."""
        response = client.post(
            "/api/ai/recommend/strategy?current_status=deployed&deployment_count=50&success_rate=95.5",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert "recommended_strategy" in data
        assert "reasoning" in data
        assert "risk_level" in data

    def test_recommend_strategy_low_success_rate(self, auth_headers):
        """Test strategy recommendation with low success rate."""
        response = client.post(
            "/api/ai/recommend/strategy?current_status=failed&deployment_count=20&success_rate=60.0",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert "recommended_strategy" in data
        # Should recommend safer strategy for low success rate
        assert data["risk_level"] in ["medium", "high"]


class TestCostOptimization:
    """Test AI cost optimization features."""

    def test_analyze_costs(self, auth_headers):
        """Test cost analysis endpoint."""
        response = client.post(
            "/api/ai/optimize/costs",
            json={
                "deployment_count": 100,
                "avg_duration_seconds": 450.0,
                "instance_types": {"t2.small": 80, "t2.medium": 20}
            },
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert "current_monthly_cost_usd" in data
        assert "potential_savings_usd" in data
        assert "optimization_suggestions" in data
        assert "priority" in data
        assert isinstance(data["optimization_suggestions"], list)

    def test_estimate_deployment_cost(self, auth_headers):
        """Test deployment cost estimation."""
        response = client.get(
            "/api/ai/optimize/estimate?instance_type=t2.small&duration_hours=2.5&environment=production",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert "instance_type" in data
        assert "total_cost_usd" in data
        assert "hourly_rate_usd" in data
        assert data["instance_type"] == "t2.small"
        assert data["duration_hours"] == 2.5


class TestRollbackAdvisor:
    """Test AI rollback recommendation."""

    def test_rollback_critical_failure(self, auth_headers):
        """Test rollback recommendation with critical failure rate."""
        response = client.post(
            "/api/ai/rollback/analyze",
            json={
                "deployment_id": "test-deploy-1",
                "failed_checks": 8,
                "total_checks": 10,
                "error_messages": ["Connection refused", "Timeout"],
                "deployment_age_minutes": 15
            },
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert "should_rollback" in data
        assert "confidence" in data
        assert "reasoning" in data
        assert "suggested_action" in data
        assert "urgency" in data
        # High failure rate should recommend rollback
        assert data["should_rollback"] == True

    def test_rollback_healthy_deployment(self, auth_headers):
        """Test rollback recommendation with healthy deployment."""
        response = client.post(
            "/api/ai/rollback/analyze",
            json={
                "deployment_id": "test-deploy-2",
                "failed_checks": 1,
                "total_checks": 20,
                "error_messages": [],
                "deployment_age_minutes": 30
            },
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        # Low failure rate should NOT recommend rollback
        assert data["should_rollback"] == False
        assert data["urgency"] == "low"

    def test_rollback_startup_grace_period(self, auth_headers):
        """Test rollback during startup grace period."""
        response = client.post(
            "/api/ai/rollback/analyze",
            json={
                "deployment_id": "test-deploy-3",
                "failed_checks": 5,
                "total_checks": 10,
                "error_messages": ["Starting up..."],
                "deployment_age_minutes": 2
            },
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        # Should not rollback during startup
        assert data["should_rollback"] == False


class TestSecurityExplainer:
    """Test AI security vulnerability explainer."""

    def test_explain_critical_vulnerability(self, auth_headers):
        """Test explanation of critical vulnerability."""
        response = client.post(
            "/api/ai/security/explain",
            json={
                "cve_id": "CVE-2024-1234",
                "package": "express",
                "severity": "CRITICAL",
                "description": "Remote code execution vulnerability"
            },
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert "simple_explanation" in data
        assert "impact" in data
        assert "fix_steps" in data
        assert "urgency" in data
        assert "recommended_timeline" in data
        assert data["urgency"] == "critical"
        assert isinstance(data["fix_steps"], list)
        assert len(data["fix_steps"]) > 0

    def test_explain_low_severity_vulnerability(self, auth_headers):
        """Test explanation of low severity vulnerability."""
        response = client.post(
            "/api/ai/security/explain",
            json={
                "cve_id": "CVE-2024-5678",
                "package": "lodash",
                "severity": "LOW",
                "description": "Minor issue"
            },
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["urgency"] == "low"
