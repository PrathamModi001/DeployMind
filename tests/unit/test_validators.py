"""
Unit tests for security validators.

Tests all validation functions to ensure they correctly:
- Accept valid inputs
- Reject invalid inputs
- Prevent injection attacks
- Sanitize sensitive data
"""

import pytest
from shared.validators import (
    SecurityValidator,
    ValidationError,
    validate_deployment_input,
    sanitize_for_logging
)


class TestRepositoryValidation:
    """Tests for repository validation"""

    def test_valid_repository(self):
        """Test valid repository formats"""
        assert SecurityValidator.validate_repository("owner/repo")
        assert SecurityValidator.validate_repository("my-org/my-app")
        assert SecurityValidator.validate_repository("user_name/app.name")
        assert SecurityValidator.validate_repository("123/456")

    def test_invalid_repository_format(self):
        """Test invalid repository formats"""
        with pytest.raises(ValidationError, match="Invalid repository format"):
            SecurityValidator.validate_repository("invalid")

        with pytest.raises(ValidationError, match="Invalid repository format"):
            SecurityValidator.validate_repository("owner/repo/extra")

        with pytest.raises(ValidationError, match="Invalid repository format"):
            SecurityValidator.validate_repository("owner@repo")

    def test_path_traversal_prevention(self):
        """Test that path traversal attempts are blocked"""
        # Path traversal attempts should be rejected (either by format check or path traversal check)
        with pytest.raises(ValidationError):
            SecurityValidator.validate_repository("../etc/passwd")

        with pytest.raises(ValidationError):
            SecurityValidator.validate_repository("owner/../admin")

        with pytest.raises(ValidationError):
            SecurityValidator.validate_repository("/etc/passwd")

    def test_repository_length_validation(self):
        """Test repository length limits"""
        # Valid: 255 characters
        long_repo = "a" * 120 + "/" + "b" * 134  # 255 total
        assert SecurityValidator.validate_repository(long_repo)

        # Invalid: 256 characters
        too_long = "a" * 120 + "/" + "b" * 135  # 256 total
        with pytest.raises(ValidationError, match="too long"):
            SecurityValidator.validate_repository(too_long)

    def test_empty_repository(self):
        """Test that empty repository is rejected"""
        with pytest.raises(ValidationError, match="non-empty string"):
            SecurityValidator.validate_repository("")

        with pytest.raises(ValidationError, match="non-empty string"):
            SecurityValidator.validate_repository(None)


class TestInstanceIdValidation:
    """Tests for AWS instance ID validation"""

    def test_valid_instance_ids(self):
        """Test valid instance ID formats"""
        assert SecurityValidator.validate_instance_id("i-1234567890abcdef0")
        assert SecurityValidator.validate_instance_id("i-12345678")
        assert SecurityValidator.validate_instance_id("i-abcdef1234567890a")

    def test_invalid_instance_id_format(self):
        """Test invalid instance ID formats"""
        with pytest.raises(ValidationError, match="Invalid instance ID"):
            SecurityValidator.validate_instance_id("invalid")

        with pytest.raises(ValidationError, match="Invalid instance ID"):
            SecurityValidator.validate_instance_id("ec2-instance")

        with pytest.raises(ValidationError, match="Invalid instance ID"):
            SecurityValidator.validate_instance_id("i-ABCDEFGH")  # Uppercase not allowed

    def test_command_injection_prevention(self):
        """Test that command injection attempts are blocked"""
        with pytest.raises(ValidationError, match="Invalid instance ID"):
            SecurityValidator.validate_instance_id("i-123; rm -rf /")

        with pytest.raises(ValidationError, match="Invalid instance ID"):
            SecurityValidator.validate_instance_id("i-123 && curl evil.com")

        with pytest.raises(ValidationError, match="Invalid instance ID"):
            SecurityValidator.validate_instance_id("$(whoami)")

    def test_empty_instance_id(self):
        """Test that empty instance ID is rejected"""
        with pytest.raises(ValidationError, match="non-empty string"):
            SecurityValidator.validate_instance_id("")

        with pytest.raises(ValidationError, match="non-empty string"):
            SecurityValidator.validate_instance_id(None)


class TestDockerTagSanitization:
    """Tests for Docker tag sanitization"""

    def test_valid_docker_tags(self):
        """Test valid Docker tags are unchanged"""
        assert SecurityValidator.sanitize_docker_tag("latest") == "latest"
        assert SecurityValidator.sanitize_docker_tag("v1.0.0") == "v1.0.0"
        assert SecurityValidator.sanitize_docker_tag("my-app_v2") == "my-app_v2"

    def test_docker_tag_sanitization(self):
        """Test that invalid characters are removed"""
        # Note: / is allowed for registry paths (e.g., docker.io/library/nginx)
        # and : is allowed for tags
        assert SecurityValidator.sanitize_docker_tag("v1.0; rm -rf /") == "v1.0rm-rf/"
        assert SecurityValidator.sanitize_docker_tag("v1.0 && curl evil") == "v1.0curlevil"
        assert SecurityValidator.sanitize_docker_tag("v1.0|cat /etc/passwd") == "v1.0cat/etc/passwd"

    def test_docker_tag_length_limit(self):
        """Test that tags are truncated to 128 characters"""
        long_tag = "a" * 200
        sanitized = SecurityValidator.sanitize_docker_tag(long_tag)
        assert len(sanitized) == 128

    def test_empty_docker_tag(self):
        """Test that empty tag defaults to 'latest'"""
        assert SecurityValidator.sanitize_docker_tag("") == "latest"
        assert SecurityValidator.sanitize_docker_tag(None) == "latest"


class TestFilePathValidation:
    """Tests for file path validation"""

    def test_valid_relative_paths(self):
        """Test valid relative paths"""
        assert SecurityValidator.validate_file_path("config.yaml")
        assert SecurityValidator.validate_file_path("configs/app.yaml")
        assert SecurityValidator.validate_file_path("data/users/profile.json")

    def test_path_traversal_prevention(self):
        """Test that path traversal is blocked"""
        with pytest.raises(ValidationError, match="Path traversal detected"):
            SecurityValidator.validate_file_path("../etc/passwd")

        with pytest.raises(ValidationError, match="Path traversal detected"):
            SecurityValidator.validate_file_path("configs/../../etc/shadow")

    def test_absolute_path_prevention(self):
        """Test that absolute paths are blocked by default"""
        with pytest.raises(ValidationError, match="Absolute paths not allowed"):
            SecurityValidator.validate_file_path("/etc/passwd")

        with pytest.raises(ValidationError, match="Absolute paths not allowed"):
            SecurityValidator.validate_file_path("C:\\Windows\\System32")

    def test_absolute_path_allowed(self):
        """Test that absolute paths can be allowed explicitly"""
        assert SecurityValidator.validate_file_path("/etc/config.yaml", allow_absolute=True)
        assert SecurityValidator.validate_file_path("C:\\app\\config.yaml", allow_absolute=True)

    def test_null_byte_prevention(self):
        """Test that null bytes are blocked"""
        with pytest.raises(ValidationError, match="Null byte detected"):
            SecurityValidator.validate_file_path("config.yaml\x00.txt")


class TestLogSanitization:
    """Tests for log message sanitization"""

    def test_api_key_redaction(self):
        """Test that API keys are redacted"""
        message = "Using API key: gsk_abc123def456"
        sanitized = SecurityValidator.sanitize_log_message(message)
        assert "gsk_***REDACTED***" in sanitized
        assert "abc123def456" not in sanitized

    def test_token_redaction(self):
        """Test that tokens are redacted"""
        message = "GitHub token: ghp_xyz789abc123"
        sanitized = SecurityValidator.sanitize_log_message(message)
        assert "ghp_***REDACTED***" in sanitized
        assert "xyz789abc123" not in sanitized

    def test_password_redaction(self):
        """Test that passwords are redacted"""
        message = "password=secret123"
        sanitized = SecurityValidator.sanitize_log_message(message)
        assert "***REDACTED***" in sanitized
        assert "secret123" not in sanitized

    def test_bearer_token_redaction(self):
        """Test that Bearer tokens are redacted"""
        message = "Authorization: Bearer abc123xyz789"
        sanitized = SecurityValidator.sanitize_log_message(message)
        assert "Bearer ***REDACTED***" in sanitized
        assert "abc123xyz789" not in sanitized

    def test_aws_key_redaction(self):
        """Test that AWS keys are redacted"""
        message = "AWS key: AKIAIOSFODNN7EXAMPLE"
        sanitized = SecurityValidator.sanitize_log_message(message)
        assert "AKIA***REDACTED***" in sanitized
        assert "IOSFODNN7EXAMPLE" not in sanitized

    def test_multiple_secrets_redaction(self):
        """Test that multiple secrets in one message are all redacted"""
        message = "api_key=gsk_abc123 password=secret123 token=ghp_xyz789"
        sanitized = SecurityValidator.sanitize_log_message(message)
        # All secrets should be redacted
        assert "***REDACTED***" in sanitized
        # Original secret values should not be present
        assert "abc123" not in sanitized
        assert "secret123" not in sanitized
        assert "xyz789" not in sanitized

    def test_case_insensitive_redaction(self):
        """Test that redaction is case-insensitive"""
        message = "API_KEY=gsk_abc123 Password=secret123"
        sanitized = SecurityValidator.sanitize_log_message(message)
        assert "***REDACTED***" in sanitized
        assert "abc123" not in sanitized
        assert "secret123" not in sanitized


class TestDeploymentStrategyValidation:
    """Tests for deployment strategy validation"""

    def test_valid_strategies(self):
        """Test valid deployment strategies"""
        assert SecurityValidator.validate_deployment_strategy("rolling")
        assert SecurityValidator.validate_deployment_strategy("blue-green")
        assert SecurityValidator.validate_deployment_strategy("canary")

    def test_case_insensitive(self):
        """Test that validation is case-insensitive"""
        assert SecurityValidator.validate_deployment_strategy("Rolling")
        assert SecurityValidator.validate_deployment_strategy("BLUE-GREEN")
        assert SecurityValidator.validate_deployment_strategy("Canary")

    def test_invalid_strategy(self):
        """Test invalid deployment strategies"""
        with pytest.raises(ValidationError, match="Invalid deployment strategy"):
            SecurityValidator.validate_deployment_strategy("invalid")

        with pytest.raises(ValidationError, match="Invalid deployment strategy"):
            SecurityValidator.validate_deployment_strategy("yolo")


class TestEnvironmentValidation:
    """Tests for environment validation"""

    def test_valid_environments(self):
        """Test valid environments"""
        assert SecurityValidator.validate_environment("development")
        assert SecurityValidator.validate_environment("staging")
        assert SecurityValidator.validate_environment("production")

    def test_case_insensitive(self):
        """Test that validation is case-insensitive"""
        assert SecurityValidator.validate_environment("Development")
        assert SecurityValidator.validate_environment("STAGING")
        assert SecurityValidator.validate_environment("Production")

    def test_invalid_environment(self):
        """Test invalid environments"""
        with pytest.raises(ValidationError, match="Invalid environment"):
            SecurityValidator.validate_environment("invalid")

        with pytest.raises(ValidationError, match="Invalid environment"):
            SecurityValidator.validate_environment("test")


class TestPortValidation:
    """Tests for port number validation"""

    def test_valid_ports(self):
        """Test valid port numbers"""
        assert SecurityValidator.validate_port(80)
        assert SecurityValidator.validate_port(443)
        assert SecurityValidator.validate_port(8080)
        assert SecurityValidator.validate_port("3000")

    def test_invalid_port_range(self):
        """Test that ports outside valid range are rejected"""
        with pytest.raises(ValidationError, match="between 1 and 65535"):
            SecurityValidator.validate_port(0)

        with pytest.raises(ValidationError, match="between 1 and 65535"):
            SecurityValidator.validate_port(65536)

        with pytest.raises(ValidationError, match="between 1 and 65535"):
            SecurityValidator.validate_port(-1)

    def test_invalid_port_type(self):
        """Test that non-integer ports are rejected"""
        with pytest.raises(ValidationError, match="must be an integer"):
            SecurityValidator.validate_port("invalid")

        with pytest.raises(ValidationError, match="must be an integer"):
            SecurityValidator.validate_port(None)


class TestUrlValidation:
    """Tests for URL validation"""

    def test_valid_urls(self):
        """Test valid URLs"""
        assert SecurityValidator.validate_url("https://example.com")
        assert SecurityValidator.validate_url("http://localhost:8080")
        assert SecurityValidator.validate_url("https://api.github.com/repos/owner/repo")

    def test_invalid_url_format(self):
        """Test invalid URL formats"""
        with pytest.raises(ValidationError, match="Invalid URL format"):
            SecurityValidator.validate_url("not a url")

        with pytest.raises(ValidationError, match="Invalid URL format"):
            SecurityValidator.validate_url("htp://example.com")

    def test_invalid_scheme(self):
        """Test that invalid schemes are rejected"""
        # Invalid schemes should be rejected (either by format or scheme check)
        with pytest.raises(ValidationError):
            SecurityValidator.validate_url("file:///etc/passwd")

        with pytest.raises(ValidationError):
            SecurityValidator.validate_url("javascript:alert(1)")

    def test_allowed_schemes(self):
        """Test custom allowed schemes"""
        assert SecurityValidator.validate_url(
            "ftp://files.example.com",
            allowed_schemes=["ftp"]
        )


class TestConvenienceFunctions:
    """Tests for convenience functions"""

    def test_validate_deployment_input_valid(self):
        """Test that valid deployment inputs pass"""
        assert validate_deployment_input(
            repo="owner/repo",
            instance_id="i-1234567890abcdef0",
            strategy="rolling"
        )

    def test_validate_deployment_input_invalid_repo(self):
        """Test that invalid repo is caught"""
        with pytest.raises(ValidationError, match="Invalid repository format"):
            validate_deployment_input(
                repo="invalid",
                instance_id="i-1234567890abcdef0",
                strategy="rolling"
            )

    def test_validate_deployment_input_invalid_instance(self):
        """Test that invalid instance ID is caught"""
        with pytest.raises(ValidationError, match="Invalid instance ID"):
            validate_deployment_input(
                repo="owner/repo",
                instance_id="invalid",
                strategy="rolling"
            )

    def test_validate_deployment_input_invalid_strategy(self):
        """Test that invalid strategy is caught"""
        with pytest.raises(ValidationError, match="Invalid deployment strategy"):
            validate_deployment_input(
                repo="owner/repo",
                instance_id="i-1234567890abcdef0",
                strategy="invalid"
            )

    def test_sanitize_for_logging(self):
        """Test that all values in dict are sanitized"""
        data = {
            "repo": "owner/repo",
            "api_key": "gsk_abc123",
            "count": 42
        }
        sanitized = sanitize_for_logging(**data)

        assert sanitized["repo"] == "owner/repo"
        assert "***REDACTED***" in sanitized["api_key"]
        assert "abc123" not in sanitized["api_key"]
        assert sanitized["count"] == 42


# Integration test
class TestSecurityValidationIntegration:
    """Integration tests for security validation"""

    def test_full_deployment_validation_flow(self):
        """Test complete validation flow for deployment"""
        # Valid inputs
        repo = "my-org/my-app"
        instance_id = "i-1234567890abcdef0"
        strategy = "rolling"
        image_tag = "v1.0.0"

        # Validate all inputs
        SecurityValidator.validate_repository(repo)
        SecurityValidator.validate_instance_id(instance_id)
        SecurityValidator.validate_deployment_strategy(strategy)
        sanitized_tag = SecurityValidator.sanitize_docker_tag(image_tag)

        # Prepare for logging
        log_data = sanitize_for_logging(
            repo=repo,
            instance_id=instance_id,
            strategy=strategy,
            image_tag=sanitized_tag,
            api_key="gsk_secret123"  # Should be redacted
        )

        # Verify sanitization
        assert log_data["repo"] == repo
        assert log_data["instance_id"] == instance_id
        assert log_data["strategy"] == strategy
        assert log_data["image_tag"] == sanitized_tag
        assert "***REDACTED***" in log_data["api_key"]
        assert "secret123" not in log_data["api_key"]

    def test_attack_prevention(self):
        """Test that common attacks are prevented"""
        # SQL injection attempt
        with pytest.raises(ValidationError):
            SecurityValidator.validate_repository("owner'; DROP TABLE deployments; --")

        # Command injection attempt
        with pytest.raises(ValidationError):
            SecurityValidator.validate_instance_id("i-123; rm -rf /")

        # Path traversal attempt
        with pytest.raises(ValidationError):
            SecurityValidator.validate_file_path("../../../etc/passwd")

        # XSS attempt in tag
        xss_tag = "<script>alert('XSS')</script>"
        sanitized = SecurityValidator.sanitize_docker_tag(xss_tag)
        assert "<script>" not in sanitized
        assert "alert" in sanitized  # Text remains, tags removed
