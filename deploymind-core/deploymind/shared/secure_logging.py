"""
Secure logging utilities that automatically redact sensitive information.

All logs should use this module instead of standard logging to prevent
credential leakage.
"""

import logging
import json
from datetime import datetime
from typing import Any, Optional
from deploymind.shared.validators import SecurityValidator


class SecureFormatter(logging.Formatter):
    """
    Custom log formatter that sanitizes sensitive data.

    Automatically redacts API keys, passwords, tokens, etc. from log messages.
    """

    def format(self, record: logging.LogRecord) -> str:
        """
        Format log record with automatic sanitization.

        Args:
            record: Log record to format

        Returns:
            Formatted and sanitized log message
        """
        # Sanitize the main message
        if isinstance(record.msg, str):
            record.msg = SecurityValidator.sanitize_log_message(record.msg)

        # Sanitize arguments
        if record.args:
            sanitized_args = []
            for arg in record.args:
                if isinstance(arg, str):
                    sanitized_args.append(
                        SecurityValidator.sanitize_log_message(arg)
                    )
                else:
                    sanitized_args.append(arg)
            record.args = tuple(sanitized_args)

        # Format with parent formatter
        return super().format(record)


class StructuredLogger:
    """
    Structured JSON logger with automatic sanitization.

    Logs in JSON format for easy parsing and analysis.
    Automatically redacts sensitive information.
    """

    def __init__(self, name: str, level: int = logging.INFO):
        """
        Initialize structured logger.

        Args:
            name: Logger name (usually __name__)
            level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        """
        self.logger = logging.getLogger(name)
        self.logger.setLevel(level)

        # Remove existing handlers
        self.logger.handlers = []

        # Add console handler with secure formatter
        handler = logging.StreamHandler()
        handler.setLevel(level)

        # Use structured JSON format
        formatter = SecureFormatter(
            fmt='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        handler.setFormatter(formatter)

        self.logger.addHandler(handler)

    def _log_structured(
        self,
        level: int,
        message: str,
        **context
    ) -> None:
        """
        Log structured message with context.

        Args:
            level: Log level
            message: Log message
            **context: Additional context (key-value pairs)
        """
        # Sanitize message
        sanitized_message = SecurityValidator.sanitize_log_message(message)

        # Sanitize context
        sanitized_context = {}
        for key, value in context.items():
            if isinstance(value, str):
                sanitized_context[key] = SecurityValidator.sanitize_log_message(value)
            else:
                sanitized_context[key] = value

        # Create structured log entry
        if sanitized_context:
            log_entry = f"{sanitized_message} | {json.dumps(sanitized_context)}"
        else:
            log_entry = sanitized_message

        self.logger.log(level, log_entry)

    def debug(self, message: str, **context) -> None:
        """Log debug message with context"""
        self._log_structured(logging.DEBUG, message, **context)

    def info(self, message: str, **context) -> None:
        """Log info message with context"""
        self._log_structured(logging.INFO, message, **context)

    def warning(self, message: str, **context) -> None:
        """Log warning message with context"""
        self._log_structured(logging.WARNING, message, **context)

    def error(self, message: str, **context) -> None:
        """Log error message with context"""
        self._log_structured(logging.ERROR, message, **context)

    def critical(self, message: str, **context) -> None:
        """Log critical message with context"""
        self._log_structured(logging.CRITICAL, message, **context)

    def exception(self, message: str, **context) -> None:
        """Log exception with stack trace"""
        # Sanitize message
        sanitized_message = SecurityValidator.sanitize_log_message(message)

        # Sanitize context
        sanitized_context = {}
        for key, value in context.items():
            if isinstance(value, str):
                sanitized_context[key] = SecurityValidator.sanitize_log_message(value)
            else:
                sanitized_context[key] = value

        if sanitized_context:
            log_entry = f"{sanitized_message} | {json.dumps(sanitized_context)}"
        else:
            log_entry = sanitized_message

        self.logger.exception(log_entry)


class AuditLogger:
    """
    Audit logger for security-critical operations.

    Logs all deployment actions to database for compliance and security analysis.
    """

    def __init__(self, deployment_id: Optional[str] = None):
        """
        Initialize audit logger.

        Args:
            deployment_id: Optional deployment ID for context
        """
        self.deployment_id = deployment_id
        self.logger = StructuredLogger(__name__)

    def log_action(
        self,
        action: str,
        actor: str,
        success: bool,
        **metadata
    ) -> None:
        """
        Log security-critical action.

        Args:
            action: Action performed (e.g., "deploy", "rollback", "scan")
            actor: Who performed the action (user ID, agent name)
            success: Whether action succeeded
            **metadata: Additional context
        """
        log_data = {
            "deployment_id": self.deployment_id,
            "action": action,
            "actor": actor,
            "success": success,
            "timestamp": datetime.utcnow().isoformat(),
            **metadata
        }

        if success:
            self.logger.info(f"Action completed: {action}", **log_data)
        else:
            self.logger.error(f"Action failed: {action}", **log_data)

        # TODO: Also write to database (deployment_logs table)
        # self._write_to_database(log_data)

    def log_security_event(
        self,
        event_type: str,
        severity: str,
        details: str,
        **metadata
    ) -> None:
        """
        Log security event (vulnerability, breach, anomaly).

        Args:
            event_type: Type of event (e.g., "vulnerability_detected")
            severity: Severity level (low, medium, high, critical)
            details: Event details
            **metadata: Additional context
        """
        log_data = {
            "deployment_id": self.deployment_id,
            "event_type": event_type,
            "severity": severity,
            "details": details,
            "timestamp": datetime.utcnow().isoformat(),
            **metadata
        }

        # Log at appropriate level based on severity
        if severity.lower() in ["high", "critical"]:
            self.logger.error(f"Security event: {event_type}", **log_data)
        elif severity.lower() == "medium":
            self.logger.warning(f"Security event: {event_type}", **log_data)
        else:
            self.logger.info(f"Security event: {event_type}", **log_data)

        # TODO: Trigger alerts for high/critical events
        if severity.lower() in ["high", "critical"]:
            self._trigger_security_alert(log_data)

    def _trigger_security_alert(self, event_data: dict) -> None:
        """
        Trigger security alert for high-severity events.

        Args:
            event_data: Event details
        """
        # TODO: Implement alerting (email, Slack, PagerDuty, etc.)
        self.logger.critical("SECURITY ALERT TRIGGERED", **event_data)


# Global logger instances
def get_logger(name: str, level: int = logging.INFO) -> StructuredLogger:
    """
    Get a structured logger instance.

    Args:
        name: Logger name (usually __name__)
        level: Log level

    Returns:
        StructuredLogger instance

    Example:
        >>> logger = get_logger(__name__)
        >>> logger.info("Deployment started", deployment_id="dep-123", repo="owner/repo")
    """
    return StructuredLogger(name, level)


def get_audit_logger(deployment_id: Optional[str] = None) -> AuditLogger:
    """
    Get an audit logger instance.

    Args:
        deployment_id: Optional deployment ID for context

    Returns:
        AuditLogger instance

    Example:
        >>> audit = get_audit_logger("dep-123")
        >>> audit.log_action("deploy", "security-agent", True, image="myapp:v1.0")
    """
    return AuditLogger(deployment_id)


# Example usage
if __name__ == "__main__":
    # Test structured logger
    logger = get_logger(__name__, level=logging.DEBUG)

    logger.debug("Debug message", step=1, action="initialize")
    logger.info("Info message", deployment_id="dep-123", status="started")
    logger.warning("Warning message", issue="high_memory_usage", value=512)
    logger.error("Error message", error="connection_timeout", retries=3)

    # Test with secrets (should be redacted)
    logger.info(
        "API call made",
        api_key="gsk_abc123def456",  # Should be redacted
        token="ghp_xyz789",  # Should be redacted
        password="secret123"  # Should be redacted
    )

    # Test audit logger
    audit = get_audit_logger("dep-123")
    audit.log_action(
        action="security_scan",
        actor="security-agent",
        success=True,
        vulnerabilities=5,
        critical=0
    )

    audit.log_security_event(
        event_type="vulnerability_detected",
        severity="high",
        details="CVE-2024-1234 detected in dependency",
        cve="CVE-2024-1234",
        package="requests"
    )
