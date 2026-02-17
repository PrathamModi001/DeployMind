"""Retry logic and circuit breaker for resilient operations."""

import time
import functools
from typing import Callable, Type, Tuple, Optional
from datetime import datetime, timedelta
from enum import Enum

from core.logger import get_logger

logger = get_logger(__name__)


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing if service recovered


class CircuitBreaker:
    """Circuit breaker to prevent cascading failures.

    Pattern:
    - CLOSED: Normal operation, track failures
    - OPEN: After failure_threshold failures, reject requests immediately
    - HALF_OPEN: After recovery_timeout, allow one test request
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        expected_exception: Type[Exception] = Exception
    ):
        """Initialize circuit breaker.

        Args:
            failure_threshold: Number of failures before opening circuit
            recovery_timeout: Seconds before attempting recovery
            expected_exception: Exception type to track
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception

        self.failure_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.state = CircuitState.CLOSED

    def call(self, func: Callable, *args, **kwargs):
        """Execute function with circuit breaker protection.

        Args:
            func: Function to execute
            *args: Positional arguments for func
            **kwargs: Keyword arguments for func

        Returns:
            Result of function execution

        Raises:
            CircuitBreakerOpen: If circuit is open
            Exception: Original exception if function fails
        """
        if self.state == CircuitState.OPEN:
            if self._should_attempt_reset():
                self.state = CircuitState.HALF_OPEN
                logger.info(f"Circuit breaker entering HALF_OPEN state")
            else:
                raise CircuitBreakerOpen(
                    f"Circuit breaker is OPEN. "
                    f"Will retry after {self.recovery_timeout}s from last failure."
                )

        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result

        except self.expected_exception as e:
            self._on_failure()
            raise

    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset."""
        if self.last_failure_time is None:
            return False

        time_since_failure = datetime.now() - self.last_failure_time
        return time_since_failure.total_seconds() >= self.recovery_timeout

    def _on_success(self):
        """Handle successful function execution."""
        if self.state == CircuitState.HALF_OPEN:
            logger.info("Circuit breaker recovered, transitioning to CLOSED")

        self.failure_count = 0
        self.state = CircuitState.CLOSED

    def _on_failure(self):
        """Handle failed function execution."""
        self.failure_count += 1
        self.last_failure_time = datetime.now()

        if self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN
            logger.warning(
                f"Circuit breaker opened after {self.failure_count} failures"
            )

    def reset(self):
        """Manually reset circuit breaker to CLOSED state."""
        self.failure_count = 0
        self.last_failure_time = None
        self.state = CircuitState.CLOSED
        logger.info("Circuit breaker manually reset to CLOSED")


class CircuitBreakerOpen(Exception):
    """Exception raised when circuit breaker is open."""
    pass


class RetryExhausted(Exception):
    """Exception raised when all retry attempts are exhausted."""
    pass


def retry(
    max_attempts: int = 3,
    delay: float = 1.0,
    exponential_backoff: bool = True,
    backoff_factor: float = 2.0,
    max_delay: float = 60.0,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
    on_retry: Optional[Callable] = None
):
    """Decorator to retry function execution on failure.

    Args:
        max_attempts: Maximum number of attempts (including first try)
        delay: Initial delay between retries in seconds
        exponential_backoff: If True, delay doubles after each retry
        backoff_factor: Multiplier for exponential backoff
        max_delay: Maximum delay between retries
        exceptions: Tuple of exception types to catch and retry
        on_retry: Optional callback function(attempt, exception, delay)

    Example:
        @retry(max_attempts=3, delay=1.0, exponential_backoff=True)
        def unstable_api_call():
            return requests.get("https://api.example.com/data")
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            attempt = 1
            current_delay = delay

            while attempt <= max_attempts:
                try:
                    return func(*args, **kwargs)

                except exceptions as e:
                    func_name = getattr(func, '__name__', 'function')
                    if attempt == max_attempts:
                        logger.error(
                            f"{func_name} failed after {max_attempts} attempts",
                            exc_info=True
                        )
                        raise RetryExhausted(
                            f"Function {func_name} failed after {max_attempts} attempts. "
                            f"Last error: {str(e)}"
                        ) from e

                    # Calculate next delay
                    if exponential_backoff:
                        current_delay = min(current_delay * backoff_factor, max_delay)

                    func_name = getattr(func, '__name__', 'function')
                    logger.warning(
                        f"{func_name} attempt {attempt}/{max_attempts} failed: {str(e)}. "
                        f"Retrying in {current_delay:.2f}s"
                    )

                    # Call retry callback if provided
                    if on_retry:
                        on_retry(attempt, e, current_delay)

                    time.sleep(current_delay)
                    attempt += 1

        return wrapper
    return decorator


def retry_with_circuit_breaker(
    max_attempts: int = 3,
    delay: float = 1.0,
    circuit_breaker: Optional[CircuitBreaker] = None,
    **retry_kwargs
):
    """Decorator combining retry logic with circuit breaker.

    Args:
        max_attempts: Maximum retry attempts
        delay: Initial delay between retries
        circuit_breaker: CircuitBreaker instance to use
        **retry_kwargs: Additional arguments for retry decorator

    Example:
        breaker = CircuitBreaker(failure_threshold=5)

        @retry_with_circuit_breaker(max_attempts=3, circuit_breaker=breaker)
        def call_external_api():
            return api.get_data()
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Use provided circuit breaker or create a new one
            cb = circuit_breaker or CircuitBreaker()

            # Create retry decorator
            retry_decorator = retry(
                max_attempts=max_attempts,
                delay=delay,
                **retry_kwargs
            )

            # Wrap function with retry
            retried_func = retry_decorator(func)

            # Execute through circuit breaker
            return cb.call(retried_func, *args, **kwargs)

        return wrapper
    return decorator


class ErrorContext:
    """Context manager for better error messages with suggestions."""

    def __init__(self, operation: str, suggestions: Optional[list] = None):
        """Initialize error context.

        Args:
            operation: Description of the operation being performed
            suggestions: List of actionable suggestions for common errors
        """
        self.operation = operation
        self.suggestions = suggestions or []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if exc_type is not None:
            # Enhance error message with context and suggestions
            error_msg = f"Error during {self.operation}: {str(exc_value)}"

            if self.suggestions:
                suggestions_text = "\n".join(f"  - {s}" for s in self.suggestions)
                error_msg += f"\n\nSuggestions:\n{suggestions_text}"

            logger.error(error_msg, exc_info=True)

            # Let the exception propagate with enhanced message
            return False  # Don't suppress exception


def get_error_suggestions(exception: Exception) -> list:
    """Get actionable suggestions based on exception type.

    Args:
        exception: The exception that occurred

    Returns:
        List of suggestion strings
    """
    import_errors = (ImportError, ModuleNotFoundError)
    connection_errors = (ConnectionError, TimeoutError)

    error_type = type(exception)
    error_msg = str(exception).lower()

    suggestions = []

    # Import/module errors
    if isinstance(exception, import_errors):
        suggestions.extend([
            "Check if required package is installed: pip install <package>",
            "Verify your virtual environment is activated",
            "Check requirements.txt for missing dependencies"
        ])

    # Connection errors
    elif isinstance(exception, connection_errors):
        suggestions.extend([
            "Check your internet connection",
            "Verify the service is running and accessible",
            "Check firewall/security group settings",
            "Verify API credentials are correct"
        ])

    # File not found
    elif isinstance(exception, FileNotFoundError):
        suggestions.extend([
            "Verify the file path is correct",
            "Check if the file exists in the specified location",
            "Ensure you have read permissions for the file"
        ])

    # Permission errors
    elif isinstance(exception, PermissionError):
        suggestions.extend([
            "Check file/directory permissions",
            "Run command with appropriate privileges if needed",
            "Verify you have write access to the target location"
        ])

    # AWS/Boto errors
    elif 'credentials' in error_msg or 'authentication' in error_msg:
        suggestions.extend([
            "Check AWS credentials: aws configure",
            "Verify IAM permissions for the operation",
            "Check if AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY are set",
            "Try refreshing your AWS credentials"
        ])

    # Docker errors
    elif 'docker' in error_msg:
        suggestions.extend([
            "Check if Docker daemon is running: docker ps",
            "Verify Docker is installed: docker --version",
            "Check Docker socket permissions",
            "Try restarting Docker service"
        ])

    # GitHub API errors
    elif 'github' in error_msg or 'repository' in error_msg:
        suggestions.extend([
            "Verify GitHub token is valid: gh auth status",
            "Check repository name format: owner/repo",
            "Ensure you have access to the repository",
            "Check GitHub API rate limits"
        ])

    # Database errors
    elif 'database' in error_msg or 'connection' in error_msg:
        suggestions.extend([
            "Check if database is running: docker-compose ps",
            "Verify database connection string in .env",
            "Try restarting database: docker-compose restart postgres",
            "Check database credentials"
        ])

    return suggestions
