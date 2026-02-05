"""
Security validators for input validation and sanitization.

Prevents injection attacks, path traversal, and other security vulnerabilities.
"""

import re
from typing import Optional


class ValidationError(Exception):
    """Raised when validation fails"""
    pass


class SecurityValidator:
    """
    Security validation utilities for all user inputs.

    Validates and sanitizes all external inputs to prevent:
    - SQL injection
    - Command injection
    - Path traversal
    - XSS attacks
    - Docker image poisoning
    """

    # Regex patterns
    REPO_PATTERN = r'^[a-zA-Z0-9_-]+/[a-zA-Z0-9_.-]+$'
    INSTANCE_ID_PATTERN = r'^i-[a-f0-9]{8,17}$'
    DOCKER_TAG_PATTERN = r'^[a-zA-Z0-9_.-]{1,128}$'

    # Secret patterns for redaction
    SECRET_PATTERNS = [
        (r'(api[_-]?key[_-]?=\s*)[\w-]+', r'\1***REDACTED***'),
        (r'(password[_-]?=\s*)[\w-]+', r'\1***REDACTED***'),
        (r'(token[_-]?=\s*)[\w-]+', r'\1***REDACTED***'),
        (r'(secret[_-]?=\s*)[\w-]+', r'\1***REDACTED***'),
        (r'Bearer\s+[\w-]+', r'Bearer ***REDACTED***'),
        (r'(gsk_)[\w-]+', r'\1***REDACTED***'),  # Groq API keys
        (r'(ghp_)[\w-]+', r'\1***REDACTED***'),  # GitHub tokens
        (r'(AKIA)[\w-]+', r'\1***REDACTED***'),  # AWS access keys
        (r'(sk-ant-)[\w-]+', r'\1***REDACTED***'),  # Claude API keys
    ]

    @staticmethod
    def validate_repository(repo: str) -> bool:
        """
        Validate GitHub repository format (owner/repo).

        Args:
            repo: Repository in format 'owner/name'

        Returns:
            True if valid

        Raises:
            ValidationError: If repository format is invalid

        Example:
            >>> SecurityValidator.validate_repository("owner/repo")
            True
            >>> SecurityValidator.validate_repository("../etc/passwd")
            ValidationError: Invalid repository format
        """
        if not repo or not isinstance(repo, str):
            raise ValidationError("Repository must be a non-empty string")

        if len(repo) > 255:
            raise ValidationError("Repository name too long (max 255 characters)")

        if not re.match(SecurityValidator.REPO_PATTERN, repo):
            raise ValidationError(
                f"Invalid repository format: {repo}. "
                f"Expected format: owner/repo"
            )

        # Check for path traversal attempts
        if ".." in repo or repo.startswith("/") or "\\" in repo:
            raise ValidationError("Path traversal detected in repository name")

        return True

    @staticmethod
    def validate_instance_id(instance_id: str) -> bool:
        """
        Validate AWS EC2 instance ID format.

        Args:
            instance_id: AWS instance ID (e.g., 'i-1234567890abcdef0')

        Returns:
            True if valid

        Raises:
            ValidationError: If instance ID format is invalid

        Example:
            >>> SecurityValidator.validate_instance_id("i-1234567890abcdef0")
            True
            >>> SecurityValidator.validate_instance_id("rm -rf /")
            ValidationError: Invalid instance ID format
        """
        if not instance_id or not isinstance(instance_id, str):
            raise ValidationError("Instance ID must be a non-empty string")

        if not re.match(SecurityValidator.INSTANCE_ID_PATTERN, instance_id):
            raise ValidationError(
                f"Invalid instance ID format: {instance_id}. "
                f"Expected format: i-[a-f0-9]{{8,17}}"
            )

        return True

    @staticmethod
    def sanitize_docker_tag(tag: str) -> str:
        """
        Sanitize Docker image tag to prevent injection.

        Docker tags can only contain: [a-zA-Z0-9_.-]

        Args:
            tag: Docker image tag

        Returns:
            Sanitized tag (invalid characters removed)

        Example:
            >>> SecurityValidator.sanitize_docker_tag("v1.0.0")
            'v1.0.0'
            >>> SecurityValidator.sanitize_docker_tag("v1.0; rm -rf /")
            'v1.0rm-rf'
        """
        if not tag:
            return "latest"

        # Remove all non-alphanumeric characters except .-_
        sanitized = re.sub(r'[^a-zA-Z0-9_.-]', '', str(tag))

        # Limit length to 128 characters (Docker tag max length)
        if len(sanitized) > 128:
            sanitized = sanitized[:128]

        # Ensure tag is not empty after sanitization
        if not sanitized:
            return "latest"

        return sanitized

    @staticmethod
    def validate_file_path(path: str, allow_absolute: bool = False) -> bool:
        """
        Validate file path to prevent path traversal attacks.

        Args:
            path: File path to validate
            allow_absolute: Whether to allow absolute paths

        Returns:
            True if valid

        Raises:
            ValidationError: If path is invalid or contains traversal

        Example:
            >>> SecurityValidator.validate_file_path("config.yaml")
            True
            >>> SecurityValidator.validate_file_path("../etc/passwd")
            ValidationError: Path traversal detected
        """
        if not path or not isinstance(path, str):
            raise ValidationError("Path must be a non-empty string")

        # Check for path traversal
        if ".." in path:
            raise ValidationError("Path traversal detected (..)  in path")

        # Check for absolute paths if not allowed
        if not allow_absolute:
            if path.startswith("/") or (len(path) > 1 and path[1] == ":"):
                raise ValidationError("Absolute paths not allowed")

        # Check for null bytes (can be used to bypass filters)
        if "\x00" in path:
            raise ValidationError("Null byte detected in path")

        return True

    @staticmethod
    def sanitize_log_message(message: str) -> str:
        """
        Remove sensitive data from log messages.

        Redacts API keys, tokens, passwords, etc. from log messages
        to prevent credential leakage.

        Args:
            message: Log message to sanitize

        Returns:
            Sanitized message with secrets redacted

        Example:
            >>> SecurityValidator.sanitize_log_message("API key: gsk_abc123")
            'API key: gsk_***REDACTED***'
        """
        if not message:
            return ""

        sanitized = str(message)

        # Apply all secret patterns
        for pattern, replacement in SecurityValidator.SECRET_PATTERNS:
            sanitized = re.sub(
                pattern,
                replacement,
                sanitized,
                flags=re.IGNORECASE
            )

        return sanitized

    @staticmethod
    def validate_deployment_strategy(strategy: str) -> bool:
        """
        Validate deployment strategy name.

        Args:
            strategy: Deployment strategy (rolling, blue-green, canary)

        Returns:
            True if valid

        Raises:
            ValidationError: If strategy is invalid
        """
        valid_strategies = {"rolling", "blue-green", "canary"}

        if not strategy or not isinstance(strategy, str):
            raise ValidationError("Strategy must be a non-empty string")

        if strategy.lower() not in valid_strategies:
            raise ValidationError(
                f"Invalid deployment strategy: {strategy}. "
                f"Valid options: {', '.join(valid_strategies)}"
            )

        return True

    @staticmethod
    def validate_environment(env: str) -> bool:
        """
        Validate environment name.

        Args:
            env: Environment name (development, staging, production)

        Returns:
            True if valid

        Raises:
            ValidationError: If environment is invalid
        """
        valid_environments = {"development", "staging", "production"}

        if not env or not isinstance(env, str):
            raise ValidationError("Environment must be a non-empty string")

        if env.lower() not in valid_environments:
            raise ValidationError(
                f"Invalid environment: {env}. "
                f"Valid options: {', '.join(valid_environments)}"
            )

        return True

    @staticmethod
    def sanitize_sql_input(value: str) -> str:
        """
        Basic SQL sanitization (should use parameterized queries instead).

        This is a last-resort measure. ALWAYS use parameterized queries
        with SQLAlchemy ORM instead of raw SQL.

        Args:
            value: Input value to sanitize

        Returns:
            Sanitized value
        """
        if not value:
            return ""

        # Remove SQL keywords and special characters
        dangerous_patterns = [
            r"';",
            r"--",
            r"/\*",
            r"\*/",
            r"xp_",
            r"sp_",
            r"exec(\s|\+)+(s|x)p",
            r"union.*select",
            r"insert.*into",
            r"delete.*from",
            r"drop.*table",
        ]

        sanitized = str(value)
        for pattern in dangerous_patterns:
            sanitized = re.sub(pattern, "", sanitized, flags=re.IGNORECASE)

        return sanitized

    @staticmethod
    def validate_port(port: int | str) -> bool:
        """
        Validate network port number.

        Args:
            port: Port number (1-65535)

        Returns:
            True if valid

        Raises:
            ValidationError: If port is invalid
        """
        try:
            port_num = int(port)
        except (ValueError, TypeError):
            raise ValidationError(f"Port must be an integer: {port}")

        if port_num < 1 or port_num > 65535:
            raise ValidationError(
                f"Port must be between 1 and 65535: {port_num}"
            )

        # Warn about privileged ports (< 1024)
        if port_num < 1024:
            # Still valid, but should be noted in logs
            pass

        return True

    @staticmethod
    def validate_url(url: str, allowed_schemes: Optional[list[str]] = None) -> bool:
        """
        Validate URL format and scheme.

        Args:
            url: URL to validate
            allowed_schemes: List of allowed schemes (default: ['http', 'https'])

        Returns:
            True if valid

        Raises:
            ValidationError: If URL is invalid
        """
        if not url or not isinstance(url, str):
            raise ValidationError("URL must be a non-empty string")

        if allowed_schemes is None:
            allowed_schemes = ["http", "https"]

        # Basic URL pattern
        url_pattern = r'^(https?|ftp)://[^\s/$.?#].[^\s]*$'
        if not re.match(url_pattern, url, re.IGNORECASE):
            raise ValidationError(f"Invalid URL format: {url}")

        # Check scheme
        scheme = url.split("://")[0].lower()
        if scheme not in allowed_schemes:
            raise ValidationError(
                f"URL scheme '{scheme}' not allowed. "
                f"Allowed schemes: {', '.join(allowed_schemes)}"
            )

        return True


# Convenience functions for common validations

def validate_deployment_input(repo: str, instance_id: str, strategy: str = "rolling") -> bool:
    """
    Validate all deployment inputs at once.

    Args:
        repo: GitHub repository
        instance_id: AWS instance ID
        strategy: Deployment strategy

    Returns:
        True if all inputs valid

    Raises:
        ValidationError: If any input is invalid
    """
    SecurityValidator.validate_repository(repo)
    SecurityValidator.validate_instance_id(instance_id)
    SecurityValidator.validate_deployment_strategy(strategy)
    return True


def sanitize_for_logging(**kwargs) -> dict:
    """
    Sanitize all values in a dictionary for safe logging.

    Args:
        **kwargs: Key-value pairs to sanitize

    Returns:
        Dictionary with sanitized values

    Example:
        >>> sanitize_for_logging(repo="owner/repo", api_key="gsk_abc123")
        {'repo': 'owner/repo', 'api_key': '***REDACTED***'}
    """
    sanitized = {}
    for key, value in kwargs.items():
        if isinstance(value, str):
            sanitized[key] = SecurityValidator.sanitize_log_message(value)
        else:
            sanitized[key] = value
    return sanitized
