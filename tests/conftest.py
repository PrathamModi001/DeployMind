"""Shared fixtures and pytest configuration for DeployMind tests."""

import os

import pytest

from core.config import Config


@pytest.fixture(autouse=True)
def mock_api_keys(monkeypatch):
    """Set dummy API keys so CrewAI agents can be instantiated in tests."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-key")


@pytest.fixture
def config():
    """Provide a test configuration with dummy values."""
    from config.settings import Settings
    return Settings(
        groq_api_key="test-groq-key",
        aws_access_key_id="AKIATEST",
        aws_secret_access_key="test-secret",
        aws_region="us-east-1",
        github_token="ghp_test_token",
        database_url="postgresql://admin:password@localhost:5432/deploymind_test",
        redis_url="redis://localhost:6379/1",
        environment="testing",
        log_level="DEBUG",
    )


@pytest.fixture
def env_vars(tmp_path):
    """Set up environment variables for testing, then clean up."""
    test_env = {
        "GROQ_API_KEY": "test-groq-key",
        "AWS_ACCESS_KEY_ID": "AKIATEST",
        "AWS_SECRET_ACCESS_KEY": "test-secret",
        "AWS_REGION": "us-east-1",
        "GITHUB_TOKEN": "ghp_test_token",
        "DATABASE_URL": "postgresql://admin:password@localhost:5432/deploymind_test",
        "REDIS_URL": "redis://localhost:6379/1",
        "ENVIRONMENT": "testing",
        "LOG_LEVEL": "DEBUG",
    }
    original = {}
    for key, value in test_env.items():
        original[key] = os.environ.get(key)
        os.environ[key] = value

    yield test_env

    for key, orig_value in original.items():
        if orig_value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = orig_value
