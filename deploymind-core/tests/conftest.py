"""Shared fixtures and pytest configuration for DeployMind tests."""

import os

import pytest


@pytest.fixture(autouse=True)
def mock_api_keys(monkeypatch):
    """Set dummy API keys so CrewAI agents can be instantiated in tests."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-key")
    monkeypatch.setenv("GROQ_API_KEY", "test-groq-key")


@pytest.fixture
def config():
    """Provide a test configuration with dummy values."""
    from deploymind.config.settings import Settings
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


@pytest.fixture(scope="session", autouse=True)
def cleanup_after_tests():
    """Cleanup temporary files after all tests complete."""
    yield  # Run all tests first

    # Cleanup after all tests
    try:
        from shared.cleanup import get_cleanup_manager
        cleanup_manager = get_cleanup_manager()

        # Clean up test artifacts
        stats = cleanup_manager.cleanup_all(
            trivy_cache_max_age_days=0,    # Clean all cache after tests
            temp_repos_max_age_hours=0,     # Clean all temp repos
            cleanup_docker=False            # Don't cleanup Docker in tests
        )

        print(f"\n✅ Test cleanup: Freed {round(stats['total_space_freed_mb'], 2)} MB")
    except Exception as e:
        print(f"\n⚠️  Test cleanup warning: {e}")
