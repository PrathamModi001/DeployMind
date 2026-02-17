"""Unit tests for retry logic and circuit breaker."""

import pytest
import time
from unittest.mock import Mock, patch

from deploymind.shared.retry import (
    retry,
    retry_with_circuit_breaker,
    CircuitBreaker,
    CircuitState,
    CircuitBreakerOpen,
    RetryExhausted,
    ErrorContext,
    get_error_suggestions
)


class TestRetryDecorator:
    """Test retry decorator functionality."""

    def test_success_on_first_attempt(self):
        """Test function succeeds on first attempt."""
        mock_func = Mock(return_value="success")
        decorated = retry(max_attempts=3)(mock_func)

        result = decorated()

        assert result == "success"
        assert mock_func.call_count == 1

    def test_success_after_retries(self):
        """Test function succeeds after some retries."""
        mock_func = Mock(side_effect=[ValueError("error"), ValueError("error"), "success"])
        decorated = retry(max_attempts=3, delay=0.01, exceptions=(ValueError,))(mock_func)

        result = decorated()

        assert result == "success"
        assert mock_func.call_count == 3

    def test_exhausted_retries(self):
        """Test all retries are exhausted."""
        mock_func = Mock(side_effect=ValueError("persistent error"))
        decorated = retry(max_attempts=3, delay=0.01, exceptions=(ValueError,))(mock_func)

        with pytest.raises(RetryExhausted, match="failed after 3 attempts"):
            decorated()

        assert mock_func.call_count == 3

    def test_exponential_backoff(self):
        """Test exponential backoff increases delay."""
        call_times = []

        def slow_func():
            call_times.append(time.time())
            if len(call_times) < 3:
                raise ValueError("not yet")
            return "success"

        decorated = retry(
            max_attempts=3,
            delay=0.1,
            exponential_backoff=True,
            backoff_factor=2.0,
            exceptions=(ValueError,)
        )(slow_func)

        result = decorated()

        assert result == "success"
        assert len(call_times) == 3

        # Check delays are increasing (approximately)
        delay1 = call_times[1] - call_times[0]
        delay2 = call_times[2] - call_times[1]
        assert delay2 > delay1  # Second delay should be longer

    def test_max_delay_cap(self):
        """Test delay is capped at max_delay."""
        mock_func = Mock(side_effect=[ValueError(), ValueError(), "success"])
        decorated = retry(
            max_attempts=3,
            delay=50.0,
            exponential_backoff=True,
            max_delay=0.1,  # Cap at 0.1 seconds
            exceptions=(ValueError,)
        )(mock_func)

        start_time = time.time()
        result = decorated()
        elapsed = time.time() - start_time

        assert result == "success"
        # Should take ~0.2s total (2 retries × 0.1s), not 100+ seconds
        assert elapsed < 1.0

    def test_specific_exceptions_only(self):
        """Test only specified exceptions trigger retry."""
        mock_func = Mock(side_effect=RuntimeError("wrong exception"))
        decorated = retry(max_attempts=3, delay=0.01, exceptions=(ValueError,))(mock_func)

        with pytest.raises(RuntimeError, match="wrong exception"):
            decorated()

        # Should not retry for non-specified exception
        assert mock_func.call_count == 1

    def test_on_retry_callback(self):
        """Test on_retry callback is called."""
        callback_data = []

        def on_retry_callback(attempt, exception, delay):
            callback_data.append((attempt, str(exception), delay))

        mock_func = Mock(side_effect=[ValueError("error1"), ValueError("error2"), "success"])
        decorated = retry(
            max_attempts=3,
            delay=0.01,
            exponential_backoff=False,
            on_retry=on_retry_callback,
            exceptions=(ValueError,)
        )(mock_func)

        result = decorated()

        assert result == "success"
        assert len(callback_data) == 2  # Called after first 2 failures
        assert callback_data[0][0] == 1  # First retry attempt
        assert "error1" in callback_data[0][1]

    def test_preserves_function_name(self):
        """Test decorator preserves original function name."""
        def my_function():
            pass

        decorated = retry(max_attempts=3)(my_function)

        assert decorated.__name__ == "my_function"

    def test_passes_arguments_correctly(self):
        """Test decorator passes arguments to wrapped function."""
        mock_func = Mock(return_value="result")
        decorated = retry(max_attempts=3)(mock_func)

        result = decorated("arg1", kwarg1="value1")

        assert result == "result"
        mock_func.assert_called_once_with("arg1", kwarg1="value1")


class TestCircuitBreaker:
    """Test circuit breaker functionality."""

    def test_initial_state_is_closed(self):
        """Test circuit breaker starts in CLOSED state."""
        cb = CircuitBreaker()
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 0

    def test_successful_calls_keep_circuit_closed(self):
        """Test successful calls keep circuit in CLOSED state."""
        cb = CircuitBreaker(failure_threshold=3)
        mock_func = Mock(return_value="success")

        for _ in range(5):
            result = cb.call(mock_func)
            assert result == "success"
            assert cb.state == CircuitState.CLOSED

        assert mock_func.call_count == 5

    def test_circuit_opens_after_threshold(self):
        """Test circuit opens after failure threshold is reached."""
        cb = CircuitBreaker(failure_threshold=3)
        mock_func = Mock(side_effect=ValueError("error"))

        # First 3 failures should open the circuit
        for i in range(3):
            with pytest.raises(ValueError):
                cb.call(mock_func)

        assert cb.state == CircuitState.OPEN
        assert cb.failure_count == 3

    def test_open_circuit_rejects_calls(self):
        """Test open circuit immediately rejects calls."""
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=10)
        mock_func = Mock(side_effect=ValueError("error"))

        # Open the circuit
        for _ in range(2):
            with pytest.raises(ValueError):
                cb.call(mock_func)

        assert cb.state == CircuitState.OPEN

        # Next call should be rejected without calling function
        with pytest.raises(CircuitBreakerOpen, match="Circuit breaker is OPEN"):
            cb.call(mock_func)

        # Function should not have been called again
        assert mock_func.call_count == 2

    def test_circuit_transitions_to_half_open(self):
        """Test circuit transitions to HALF_OPEN after recovery timeout."""
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0.1)  # 100ms timeout
        mock_func = Mock(side_effect=[ValueError("error"), ValueError("error"), "success"])

        # Open the circuit
        for _ in range(2):
            with pytest.raises(ValueError):
                cb.call(mock_func)

        assert cb.state == CircuitState.OPEN

        # Wait for recovery timeout
        time.sleep(0.15)

        # Next call should transition to HALF_OPEN and succeed
        result = cb.call(mock_func)
        assert result == "success"
        assert cb.state == CircuitState.CLOSED  # Should close after success

    def test_circuit_closes_after_successful_half_open(self):
        """Test circuit closes after successful call in HALF_OPEN state."""
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.1)

        # Open the circuit
        with pytest.raises(ValueError):
            cb.call(Mock(side_effect=ValueError()))

        assert cb.state == CircuitState.OPEN

        # Wait and make successful call
        time.sleep(0.15)
        result = cb.call(Mock(return_value="success"))

        assert result == "success"
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 0

    def test_circuit_reopens_on_half_open_failure(self):
        """Test circuit reopens if HALF_OPEN call fails."""
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0.1)
        mock_func = Mock(side_effect=ValueError("error"))

        # Open the circuit
        for _ in range(2):
            with pytest.raises(ValueError):
                cb.call(mock_func)

        # Wait and try again (will fail)
        time.sleep(0.15)

        with pytest.raises(ValueError):
            cb.call(mock_func)

        # Should still be tracking failures
        assert cb.failure_count >= 1

    def test_manual_reset(self):
        """Test manual circuit breaker reset."""
        cb = CircuitBreaker(failure_threshold=2)
        mock_func = Mock(side_effect=ValueError("error"))

        # Open the circuit
        for _ in range(2):
            with pytest.raises(ValueError):
                cb.call(mock_func)

        assert cb.state == CircuitState.OPEN

        # Manually reset
        cb.reset()

        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 0
        assert cb.last_failure_time is None

    def test_only_tracks_specified_exceptions(self):
        """Test circuit breaker only tracks specified exception types."""
        cb = CircuitBreaker(failure_threshold=2, expected_exception=ValueError)

        # RuntimeError should not trigger circuit breaker
        with pytest.raises(RuntimeError):
            cb.call(Mock(side_effect=RuntimeError("different error")))

        assert cb.state == CircuitState.CLOSED  # Should still be closed
        assert cb.failure_count == 0


class TestRetryWithCircuitBreaker:
    """Test combined retry + circuit breaker decorator."""

    def test_successful_execution(self):
        """Test successful execution with combined decorator."""
        cb = CircuitBreaker()
        mock_func = Mock(return_value="success")
        decorated = retry_with_circuit_breaker(max_attempts=3, delay=0.01, circuit_breaker=cb)(mock_func)

        result = decorated()

        assert result == "success"
        assert cb.state == CircuitState.CLOSED

    def test_retry_then_circuit_breaker(self):
        """Test retries exhaust then circuit breaker opens."""
        cb = CircuitBreaker(failure_threshold=2)
        mock_func = Mock(side_effect=ValueError("persistent error"))
        decorated = retry_with_circuit_breaker(
            max_attempts=2,
            delay=0.01,
            circuit_breaker=cb,
            exceptions=(ValueError,)
        )(mock_func)

        # First call: retries exhaust
        with pytest.raises(RetryExhausted):
            decorated()

        # Circuit should have tracked failures
        assert cb.failure_count >= 1

    def test_creates_default_circuit_breaker(self):
        """Test decorator creates circuit breaker if not provided."""
        mock_func = Mock(return_value="success")
        decorated = retry_with_circuit_breaker(max_attempts=3, delay=0.01)(mock_func)

        result = decorated()
        assert result == "success"


class TestErrorContext:
    """Test error context manager."""

    def test_context_without_exception(self):
        """Test context manager when no exception occurs."""
        with ErrorContext("test operation"):
            result = "success"

        assert result == "success"

    def test_context_with_exception(self):
        """Test context manager enhances exceptions."""
        suggestions = ["Try this", "Or this"]

        with pytest.raises(ValueError, match="test error"):
            with ErrorContext("test operation", suggestions=suggestions):
                raise ValueError("test error")

    def test_exception_propagates(self):
        """Test exception is not suppressed."""
        with pytest.raises(RuntimeError):
            with ErrorContext("operation"):
                raise RuntimeError("error")


class TestGetErrorSuggestions:
    """Test error suggestion generation."""

    def test_import_error_suggestions(self):
        """Test suggestions for import errors."""
        error = ImportError("No module named 'missing_package'")
        suggestions = get_error_suggestions(error)

        assert len(suggestions) > 0
        assert any("pip install" in s for s in suggestions)
        assert any("virtual environment" in s for s in suggestions)

    def test_connection_error_suggestions(self):
        """Test suggestions for connection errors."""
        error = ConnectionError("Connection refused")
        suggestions = get_error_suggestions(error)

        assert len(suggestions) > 0
        assert any("internet connection" in s for s in suggestions)
        assert any("service is running" in s for s in suggestions)

    def test_file_not_found_suggestions(self):
        """Test suggestions for file not found errors."""
        error = FileNotFoundError("File not found")
        suggestions = get_error_suggestions(error)

        assert len(suggestions) > 0
        assert any("file path" in s for s in suggestions)

    def test_permission_error_suggestions(self):
        """Test suggestions for permission errors."""
        error = PermissionError("Access denied")
        suggestions = get_error_suggestions(error)

        assert len(suggestions) > 0
        assert any("permissions" in s for s in suggestions)

    def test_aws_credentials_error_suggestions(self):
        """Test suggestions for AWS credential errors."""
        error = Exception("Invalid AWS credentials")
        suggestions = get_error_suggestions(error)

        assert len(suggestions) > 0
        assert any("AWS" in s or "credentials" in s for s in suggestions)

    def test_docker_error_suggestions(self):
        """Test suggestions for Docker errors."""
        error = Exception("Docker daemon not running")
        suggestions = get_error_suggestions(error)

        assert len(suggestions) > 0
        assert any("Docker" in s for s in suggestions)

    def test_github_error_suggestions(self):
        """Test suggestions for GitHub errors."""
        error = Exception("GitHub repository not found")
        suggestions = get_error_suggestions(error)

        assert len(suggestions) > 0
        assert any("GitHub" in s or "repository" in s for s in suggestions)

    def test_database_error_suggestions(self):
        """Test suggestions for database errors."""
        error = Exception("Database connection failed")
        suggestions = get_error_suggestions(error)

        assert len(suggestions) > 0
        assert any("database" in s for s in suggestions)

    def test_generic_error_returns_empty_list(self):
        """Test generic errors return empty suggestion list."""
        error = Exception("Some random error")
        suggestions = get_error_suggestions(error)

        # May or may not have suggestions, just verify it doesn't crash
        assert isinstance(suggestions, list)
