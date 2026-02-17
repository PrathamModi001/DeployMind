"""Tests for configuration loading."""

import pytest

from deploymind.config.settings import Settings


@pytest.mark.unit
class TestConfig:
    def test_default_values(self):
        """Settings should have sensible defaults."""
        settings = Settings()
        assert settings.aws_region == "us-east-1"
        assert settings.environment == "development"
        assert settings.log_level == "INFO"
        assert settings.max_deployment_time_seconds == 300
        assert settings.health_check_interval_seconds == 10

    def test_load_from_env(self, env_vars):
        """Settings.load() should read from environment variables."""
        settings = Settings.load()
        assert settings.groq_api_key == "test-groq-key"
        assert settings.aws_access_key_id == "AKIATEST"
        assert settings.aws_region == "us-east-1"
        assert settings.github_token == "ghp_test_token"
        assert settings.environment == "testing"

    def test_validate_missing_keys(self):
        """validate() should report missing required variables."""
        settings = Settings()
        missing = settings.validate()
        assert "GROQ_API_KEY" in missing
        assert "AWS_ACCESS_KEY_ID" in missing
        assert "AWS_SECRET_ACCESS_KEY" in missing
        assert "GITHUB_TOKEN" in missing

    def test_validate_all_present(self, config):
        """validate() should return empty list when all keys present."""
        missing = config.validate()
        assert missing == []

    def test_is_production(self):
        """is_production should reflect environment setting."""
        settings = Settings(environment="production")
        assert settings.is_production is True

        settings = Settings(environment="development")
        assert settings.is_production is False

    def test_load_from_env_file(self, tmp_path, monkeypatch):
        """Settings.load() should read from a .env file."""
        monkeypatch.delenv("GROQ_API_KEY", raising=False)
        monkeypatch.delenv("AWS_REGION", raising=False)
        env_file = tmp_path / ".env"
        env_file.write_text(
            "GROQ_API_KEY=test-groq-from-file\n"
            "AWS_REGION=eu-west-1\n"
        )
        settings = Settings.load(env_file=str(env_file))
        assert settings.groq_api_key == "test-groq-from-file"
        assert settings.aws_region == "eu-west-1"
