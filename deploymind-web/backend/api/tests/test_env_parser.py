"""Tests for .env file parser and upload endpoints."""
import pytest
from fastapi.testclient import TestClient
from io import BytesIO

from api.main import app
from api.models.user import User
from api.models.environment_variable import EnvironmentVariable
from api.services.database import get_db
from api.services.env_parser import EnvFileParser
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
        email="env_parser_test@example.com",
        username="envparsertest",
        github_id="777888999",
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


class TestEnvFileParser:
    """Test EnvFileParser class directly."""

    def test_parse_simple_env_file(self):
        """Test parsing simple .env file."""
        content = """
DATABASE_URL=postgresql://localhost/db
PORT=3000
NODE_ENV=production
        """
        parser = EnvFileParser()
        variables = parser.parse_env_file(content)

        assert len(variables) == 3
        assert variables[0]["key"] == "DATABASE_URL"
        assert variables[0]["value"] == "postgresql://localhost/db"
        assert variables[1]["key"] == "PORT"
        assert variables[1]["value"] == "3000"

    def test_secret_detection(self):
        """Test automatic secret detection."""
        content = """
DATABASE_PASSWORD=secret123
API_KEY=abc123
PUBLIC_URL=https://example.com
SECRET_TOKEN=xyz789
        """
        parser = EnvFileParser()
        variables = parser.parse_env_file(content)

        # Check secrets detected
        password_var = next(v for v in variables if v["key"] == "DATABASE_PASSWORD")
        assert password_var["is_secret"] == True

        api_key_var = next(v for v in variables if v["key"] == "API_KEY")
        assert api_key_var["is_secret"] == True

        # Public URL should not be secret
        public_url_var = next(v for v in variables if v["key"] == "PUBLIC_URL")
        assert public_url_var["is_secret"] == False

    def test_quote_removal(self):
        """Test removal of quotes from values."""
        content = """
SINGLE='value with single quotes'
DOUBLE="value with double quotes"
BACKTICK=`value with backticks`
NO_QUOTES=value without quotes
        """
        parser = EnvFileParser()
        variables = parser.parse_env_file(content)

        assert variables[0]["value"] == "value with single quotes"
        assert variables[1]["value"] == "value with double quotes"
        assert variables[2]["value"] == "value with backticks"
        assert variables[3]["value"] == "value without quotes"

    def test_comment_lines_ignored(self):
        """Test that comment lines are ignored."""
        content = """
# This is a comment
DATABASE_URL=postgresql://localhost/db
# Another comment
PORT=3000
        """
        parser = EnvFileParser()
        variables = parser.parse_env_file(content)

        assert len(variables) == 2  # Only 2 variables, no comments

    def test_empty_lines_ignored(self):
        """Test that empty lines are ignored."""
        content = """
DATABASE_URL=postgresql://localhost/db

PORT=3000


NODE_ENV=production
        """
        parser = EnvFileParser()
        variables = parser.parse_env_file(content)

        assert len(variables) == 3

    def test_invalid_key_format(self):
        """Test that invalid keys are rejected."""
        content = """
VALID_KEY=value1
123_INVALID=value2
INVALID-KEY=value3
VALID_KEY_2=value4
        """
        parser = EnvFileParser()
        variables = parser.parse_env_file(content)

        # Only valid keys should be parsed
        keys = [v["key"] for v in variables]
        assert "VALID_KEY" in keys
        assert "VALID_KEY_2" in keys
        assert "123_INVALID" not in keys
        assert "INVALID-KEY" not in keys

    def test_equals_in_value(self):
        """Test values containing equals sign."""
        content = """
CONNECTION_STRING=Server=localhost;Database=db
        """
        parser = EnvFileParser()
        variables = parser.parse_env_file(content)

        assert len(variables) == 1
        assert variables[0]["value"] == "Server=localhost;Database=db"

    def test_validate_env_file(self):
        """Test file validation."""
        content = """
# Comment
VALID_KEY=value

ANOTHER_KEY=value2
        """
        parser = EnvFileParser()
        validation = parser.validate_env_file(content)

        assert validation["is_valid"] == True
        assert validation["valid_variables"] == 2
        assert validation["comment_lines"] == 1

    def test_validate_invalid_file(self):
        """Test validation of invalid file."""
        content = """
VALID_KEY=value
123_INVALID=value
INVALID-KEY=value
        """
        parser = EnvFileParser()
        validation = parser.validate_env_file(content)

        assert validation["is_valid"] == False
        assert validation["valid_variables"] == 1
        assert validation["invalid_lines"] == 2


class TestEnvFileUpload:
    """Test .env file upload endpoints."""

    def test_upload_env_file_success(self, auth_headers):
        """Test successful .env file upload."""
        env_content = b"""
DATABASE_URL=postgresql://localhost/db
API_KEY=secret123
PORT=3000
        """
        files = {"file": ("test.env", BytesIO(env_content), "text/plain")}

        response = client.post(
            "/api/uploads/env/test-deploy-1",
            files=files,
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["uploaded"] == 3
        assert len(data["variables"]) == 3

        # Check secret is masked
        api_key_var = next(v for v in data["variables"] if v["key"] == "API_KEY")
        assert api_key_var["value"] == "••••••••"
        assert api_key_var["is_secret"] == True

    def test_upload_env_file_no_auth(self):
        """Test upload without authentication."""
        env_content = b"DATABASE_URL=postgresql://localhost/db"
        files = {"file": ("test.env", BytesIO(env_content), "text/plain")}

        response = client.post(
            "/api/uploads/env/test-deploy-1",
            files=files
        )

        assert response.status_code == 401

    def test_upload_invalid_file_type(self, auth_headers):
        """Test upload with invalid file type."""
        files = {"file": ("test.txt", BytesIO(b"content"), "text/plain")}

        response = client.post(
            "/api/uploads/env/test-deploy-1",
            files=files,
            headers=auth_headers
        )

        assert response.status_code == 400
        assert "Invalid file type" in response.json()["detail"]

    def test_upload_invalid_encoding(self, auth_headers):
        """Test upload with invalid encoding."""
        # Create binary content that's not valid UTF-8
        invalid_content = b"\x80\x81\x82\x83"
        files = {"file": ("test.env", BytesIO(invalid_content), "text/plain")}

        response = client.post(
            "/api/uploads/env/test-deploy-1",
            files=files,
            headers=auth_headers
        )

        assert response.status_code == 400
        assert "encoding" in response.json()["detail"].lower()

    def test_upload_duplicate_keys(self, auth_headers):
        """Test uploading env file with duplicate keys updates existing."""
        # First upload
        env_content_1 = b"PORT=3000\nNODE_ENV=development"
        files = {"file": ("test.env", BytesIO(env_content_1), "text/plain")}

        response1 = client.post(
            "/api/uploads/env/test-deploy-1",
            files=files,
            headers=auth_headers
        )
        assert response1.status_code == 200

        # Second upload with same key, different value
        env_content_2 = b"PORT=8000\nNODE_ENV=production"
        files = {"file": ("test.env", BytesIO(env_content_2), "text/plain")}

        response2 = client.post(
            "/api/uploads/env/test-deploy-1",
            files=files,
            headers=auth_headers
        )

        assert response2.status_code == 200
        # Should still be 2 variables (updated, not duplicated)
        data = response2.json()
        assert data["uploaded"] == 2

    def test_validate_env_file_endpoint(self, auth_headers):
        """Test .env file validation endpoint."""
        env_content = b"""
DATABASE_URL=postgresql://localhost/db
API_KEY=secret123
        """
        files = {"file": ("test.env", BytesIO(env_content), "text/plain")}

        response = client.post(
            "/api/uploads/env/test-deploy-1/validate",
            files=files,
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert "validation" in data
        assert "preview" in data
        assert data["validation"]["is_valid"] == True
        assert len(data["preview"]) == 2

    def test_empty_env_file(self, auth_headers):
        """Test uploading empty .env file."""
        env_content = b""
        files = {"file": ("test.env", BytesIO(env_content), "text/plain")}

        response = client.post(
            "/api/uploads/env/test-deploy-1",
            files=files,
            headers=auth_headers
        )

        # Should succeed but upload 0 variables
        assert response.status_code == 200
        data = response.json()
        assert data["uploaded"] == 0


class TestEnvParserEdgeCases:
    """Test edge cases for env parser."""

    def test_very_long_value(self):
        """Test parsing very long values."""
        long_value = "x" * 10000
        content = f"LONG_VALUE={long_value}"

        parser = EnvFileParser()
        variables = parser.parse_env_file(content)

        assert len(variables) == 1
        assert variables[0]["value"] == long_value

    def test_special_characters_in_value(self):
        """Test values with special characters."""
        content = """
URL=https://example.com?foo=bar&baz=qux
JSON={"key": "value", "nested": {"a": 1}}
        """
        parser = EnvFileParser()
        variables = parser.parse_env_file(content)

        assert len(variables) == 2
        assert "?" in variables[0]["value"]
        assert "{" in variables[1]["value"]

    def test_multiline_value_not_supported(self):
        """Test that multiline values are not supported."""
        content = """
KEY1=value1
KEY2=line1
line2
KEY3=value3
        """
        parser = EnvFileParser()
        variables = parser.parse_env_file(content)

        # line2 should be ignored (invalid format)
        keys = [v["key"] for v in variables]
        assert "KEY1" in keys
        assert "KEY2" in keys
        assert "KEY3" in keys
        assert "line2" not in str(variables)
