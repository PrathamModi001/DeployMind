"""Custom exceptions for DeployMind."""


class DeployMindException(Exception):
    """Base exception for DeployMind."""
    pass


class DeploymentError(DeployMindException):
    """Deployment-related errors."""
    pass


class SecurityScanError(DeployMindException):
    """Security scanning errors."""
    pass


class BuildError(DeployMindException):
    """Build-related errors."""
    pass


class ConfigurationError(DeployMindException):
    """Configuration errors."""
    pass


class ValidationError(DeployMindException):
    """Input validation errors."""
    pass
