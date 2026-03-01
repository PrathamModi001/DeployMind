"""Tests for environment variables management."""
import pytest
from fastapi.testclient import TestClient
import sys
from pathlib import Path

from api.main import app
from api.models.user import User
from api.models.environment_variable import EnvironmentVariable
from api.services.database import get_db
from api.utils.jwt import create_access_token
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Add deploymind-core to path
core_path = Path(__file__).parent.parent.parent.parent / "deploymind-core"
sys.path.insert(0, str(core_path))

try:
    from deploymind.infrastructure.database.connection import Base as CoreBase
    CORE_AVAILABLE = True
except ImportError:
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

# Create all tables from deploymind-core (includes deployments for FK)
if CORE_AVAILABLE and CoreBase:
    CoreBase.metadata.create_all(bind=engine)
else:
    # Fallback
    User.__table__.create(bind=engine, checkfirst=True)
    EnvironmentVariable.__table__.create(bind=engine, checkfirst=True)


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
        email="env_test@example.com",
        username="envtest",
        github_id="88888888",
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
    db.query(EnvironmentVariable).delete()
    db.commit()
    db.close()
    yield


class TestEnvironmentVariables:
    """Test environment variables CRUD operations."""

    def test_list_env_vars_empty(self, auth_headers):
        """Test listing environment variables when none exist."""
        response = client.get(
            "/api/deployments/deploy-123/env",
            headers=auth_headers
        )

        assert response.status_code == 200
        assert response.json() == []

    def test_create_env_var(self, auth_headers):
        """Test creating an environment variable."""
        response = client.post(
            "/api/deployments/deploy-123/env",
            json={
                "key": "DATABASE_URL",
                "value": "postgres://localhost/db",
                "is_secret": False
            },
            headers=auth_headers
        )

        assert response.status_code == 201
        data = response.json()
        assert data["key"] == "DATABASE_URL"
        assert data["value"] == "postgres://localhost/db"
        assert data["is_secret"] == False

    def test_create_secret_env_var(self, auth_headers):
        """Test creating a secret environment variable."""
        response = client.post(
            "/api/deployments/deploy-123/env",
            json={
                "key": "API_KEY",
                "value": "secret123",
                "is_secret": True
            },
            headers=auth_headers
        )

        assert response.status_code == 201
        data = response.json()
        assert data["key"] == "API_KEY"
        assert data["value"] == "••••••••"  # Masked
        assert data["is_secret"] == True

    def test_create_duplicate_key(self, auth_headers):
        """Test creating a duplicate environment variable."""
        # Create first variable
        client.post(
            "/api/deployments/deploy-123/env",
            json={"key": "PORT", "value": "3000", "is_secret": False},
            headers=auth_headers
        )

        # Try to create duplicate
        response = client.post(
            "/api/deployments/deploy-123/env",
            json={"key": "PORT", "value": "8000", "is_secret": False},
            headers=auth_headers
        )

        assert response.status_code == 400
        assert "already exists" in response.json()["detail"]

    def test_list_env_vars_with_data(self, auth_headers):
        """Test listing environment variables."""
        # Create some variables
        client.post(
            "/api/deployments/deploy-123/env",
            json={"key": "NODE_ENV", "value": "production", "is_secret": False},
            headers=auth_headers
        )
        client.post(
            "/api/deployments/deploy-123/env",
            json={"key": "SECRET_KEY", "value": "abc123", "is_secret": True},
            headers=auth_headers
        )

        response = client.get(
            "/api/deployments/deploy-123/env",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

        # Check secret is masked
        secret_var = next(v for v in data if v["key"] == "SECRET_KEY")
        assert secret_var["value"] == "••••••••"

    def test_update_env_var(self, auth_headers):
        """Test updating an environment variable."""
        # Create variable
        create_response = client.post(
            "/api/deployments/deploy-123/env",
            json={"key": "DEBUG", "value": "false", "is_secret": False},
            headers=auth_headers
        )
        env_id = create_response.json()["id"]

        # Update variable
        response = client.put(
            f"/api/deployments/deploy-123/env/{env_id}",
            json={"key": "DEBUG", "value": "true", "is_secret": False},
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["value"] == "true"

    def test_delete_env_var(self, auth_headers):
        """Test deleting an environment variable."""
        # Create variable
        create_response = client.post(
            "/api/deployments/deploy-123/env",
            json={"key": "TEMP_VAR", "value": "temp", "is_secret": False},
            headers=auth_headers
        )
        env_id = create_response.json()["id"]

        # Delete variable
        response = client.delete(
            f"/api/deployments/deploy-123/env/{env_id}",
            headers=auth_headers
        )

        assert response.status_code == 204

        # Verify deletion
        list_response = client.get(
            "/api/deployments/deploy-123/env",
            headers=auth_headers
        )
        assert len(list_response.json()) == 0

    def test_delete_nonexistent_env_var(self, auth_headers):
        """Test deleting a nonexistent environment variable."""
        response = client.delete(
            "/api/deployments/deploy-123/env/99999",
            headers=auth_headers
        )

        assert response.status_code == 404

    def test_env_vars_no_auth(self):
        """Test environment variables endpoints without authentication."""
        response = client.get("/api/deployments/deploy-123/env")
        assert response.status_code == 401
