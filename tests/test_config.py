"""Tests for configuration loading."""

import pytest

from core.config import Config


@pytest.mark.unit
class TestConfig:
    def test_default_values(self):
        """Config should have sensible defaults."""
        config = Config()
        assert config.aws_region == "us-east-1"
        assert config.environment == "development"
        assert config.log_level == "INFO"
        assert config.max_deployment_time_seconds == 300
        assert config.health_check_interval_seconds == 10

    def test_load_from_env(self, env_vars):
        """Config.load() should read from environment variables."""
        config = Config.load()
        assert config.anthropic_api_key == "sk-ant-test-key"
        assert config.aws_access_key_id == "AKIATEST"
        assert config.aws_region == "us-east-1"
        assert config.github_token == "ghp_test_token"
        assert config.environment == "testing"

    def test_validate_missing_keys(self):
        """validate() should report missing required variables."""
        config = Config()
        missing = config.validate()
        assert "ANTHROPIC_API_KEY" in missing
        assert "AWS_ACCESS_KEY_ID" in missing
        assert "AWS_SECRET_ACCESS_KEY" in missing
        assert "GITHUB_TOKEN" in missing

    def test_validate_all_present(self, config):
        """validate() should return empty list when all keys present."""
        missing = config.validate()
        assert missing == []

    def test_is_production(self):
        """is_production should reflect environment setting."""
        config = Config(environment="production")
        assert config.is_production is True

        config = Config(environment="development")
        assert config.is_production is False

    def test_load_from_env_file(self, tmp_path, monkeypatch):
        """Config.load() should read from a .env file."""
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("AWS_REGION", raising=False)
        env_file = tmp_path / ".env"
        env_file.write_text(
            "ANTHROPIC_API_KEY=sk-ant-from-file\n"
            "AWS_REGION=eu-west-1\n"
        )
        config = Config.load(env_file=str(env_file))
        assert config.anthropic_api_key == "sk-ant-from-file"
        assert config.aws_region == "eu-west-1"
