"""Health check system for deployed applications.

Supports multiple check types:
- HTTP: Check HTTP endpoints (GET requests)
- TCP: Check TCP port connectivity
- Command: Execute commands on EC2 instances (via SSM)
"""

import time
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Literal
import requests
import socket

from shared.secure_logging import get_logger

logger = get_logger(__name__)


@dataclass
class HealthCheckResult:
    """Result of a health check operation."""

    check_type: Literal["http", "tcp", "command"]
    healthy: bool
    status_code: Optional[int] = None
    response_time_ms: Optional[int] = None
    response_body: Optional[str] = None
    error_message: Optional[str] = None
    instance_state: Optional[str] = None
    instance_status: Optional[str] = None
    attempt_number: int = 1
    max_attempts: int = 5
    check_time: datetime = None

    def __post_init__(self):
        if self.check_time is None:
            self.check_time = datetime.utcnow()


class HealthChecker:
    """Health check system for deployed applications.

    Provides multiple health check mechanisms:
    1. HTTP checks - GET requests to health endpoints
    2. TCP checks - Port connectivity checks
    3. Command checks - Execute health commands via EC2 SSM

    Supports retries, timeouts, and detailed result tracking.
    """

    def __init__(self, timeout: int = 30, max_retries: int = 5, retry_delay: int = 10):
        """Initialize health checker.

        Args:
            timeout: Request timeout in seconds (default: 30)
            max_retries: Maximum retry attempts (default: 5)
            retry_delay: Delay between retries in seconds (default: 10)
        """
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        logger.info(
            "HealthChecker initialized",
            extra={
                "timeout": timeout,
                "max_retries": max_retries,
                "retry_delay": retry_delay
            }
        )

    def check_http(
        self,
        url: str,
        expected_status: int = 200,
        max_response_time_ms: int = 5000
    ) -> HealthCheckResult:
        """Perform HTTP health check with retries.

        Args:
            url: Health check URL (e.g., http://ec2-ip:8080/health)
            expected_status: Expected HTTP status code (default: 200)
            max_response_time_ms: Maximum acceptable response time (default: 5000ms)

        Returns:
            HealthCheckResult with check details
        """
        logger.info(f"Starting HTTP health check", extra={"url": url, "expected_status": expected_status})

        for attempt in range(1, self.max_retries + 1):
            try:
                start_time = time.time()
                response = requests.get(url, timeout=self.timeout)
                response_time_ms = int((time.time() - start_time) * 1000)

                # Determine if healthy
                status_match = response.status_code == expected_status
                response_time_ok = response_time_ms <= max_response_time_ms
                healthy = status_match and response_time_ok

                result = HealthCheckResult(
                    check_type="http",
                    healthy=healthy,
                    status_code=response.status_code,
                    response_time_ms=response_time_ms,
                    response_body=response.text[:500] if response.text else None,
                    attempt_number=attempt,
                    max_attempts=self.max_retries
                )

                if healthy:
                    logger.info(
                        "HTTP health check passed",
                        extra={
                            "url": url,
                            "status_code": response.status_code,
                            "response_time_ms": response_time_ms,
                            "attempt": attempt
                        }
                    )
                    return result
                else:
                    error_msg = []
                    if not status_match:
                        error_msg.append(f"Status {response.status_code}, expected {expected_status}")
                    if not response_time_ok:
                        error_msg.append(f"Response time {response_time_ms}ms > {max_response_time_ms}ms")

                    result.error_message = "; ".join(error_msg)
                    logger.warning(
                        "HTTP health check failed",
                        extra={
                            "url": url,
                            "error": result.error_message,
                            "attempt": attempt
                        }
                    )

                    if attempt < self.max_retries:
                        logger.info(f"Retrying in {self.retry_delay}s...")
                        time.sleep(self.retry_delay)
                    else:
                        return result

            except requests.exceptions.RequestException as e:
                error_message = f"HTTP request failed: {str(e)}"
                logger.warning(
                    "HTTP health check exception",
                    extra={"url": url, "error": error_message, "attempt": attempt}
                )

                if attempt < self.max_retries:
                    logger.info(f"Retrying in {self.retry_delay}s...")
                    time.sleep(self.retry_delay)
                else:
                    return HealthCheckResult(
                        check_type="http",
                        healthy=False,
                        error_message=error_message,
                        attempt_number=attempt,
                        max_attempts=self.max_retries
                    )

        # Should never reach here
        return HealthCheckResult(
            check_type="http",
            healthy=False,
            error_message="Max retries exceeded",
            attempt_number=self.max_retries,
            max_attempts=self.max_retries
        )

    def check_tcp(self, host: str, port: int) -> HealthCheckResult:
        """Perform TCP port connectivity check with retries.

        Args:
            host: Host IP or DNS name
            port: Port number to check

        Returns:
            HealthCheckResult with check details
        """
        logger.info(f"Starting TCP health check", extra={"host": host, "port": port})

        for attempt in range(1, self.max_retries + 1):
            try:
                start_time = time.time()
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(self.timeout)
                result = sock.connect_ex((host, port))
                response_time_ms = int((time.time() - start_time) * 1000)
                sock.close()

                healthy = result == 0

                if healthy:
                    logger.info(
                        "TCP health check passed",
                        extra={
                            "host": host,
                            "port": port,
                            "response_time_ms": response_time_ms,
                            "attempt": attempt
                        }
                    )
                    return HealthCheckResult(
                        check_type="tcp",
                        healthy=True,
                        response_time_ms=response_time_ms,
                        attempt_number=attempt,
                        max_attempts=self.max_retries
                    )
                else:
                    error_message = f"Port {port} not reachable (error code: {result})"
                    logger.warning(
                        "TCP health check failed",
                        extra={"host": host, "port": port, "error": error_message, "attempt": attempt}
                    )

                    if attempt < self.max_retries:
                        logger.info(f"Retrying in {self.retry_delay}s...")
                        time.sleep(self.retry_delay)
                    else:
                        return HealthCheckResult(
                            check_type="tcp",
                            healthy=False,
                            error_message=error_message,
                            response_time_ms=response_time_ms,
                            attempt_number=attempt,
                            max_attempts=self.max_retries
                        )

            except socket.error as e:
                error_message = f"TCP connection failed: {str(e)}"
                logger.warning(
                    "TCP health check exception",
                    extra={"host": host, "port": port, "error": error_message, "attempt": attempt}
                )

                if attempt < self.max_retries:
                    logger.info(f"Retrying in {self.retry_delay}s...")
                    time.sleep(self.retry_delay)
                else:
                    return HealthCheckResult(
                        check_type="tcp",
                        healthy=False,
                        error_message=error_message,
                        attempt_number=attempt,
                        max_attempts=self.max_retries
                    )

        return HealthCheckResult(
            check_type="tcp",
            healthy=False,
            error_message="Max retries exceeded",
            attempt_number=self.max_retries,
            max_attempts=self.max_retries
        )

    def check_command(
        self,
        ec2_client,
        instance_id: str,
        command: str,
        expected_output: Optional[str] = None,
        expected_exit_code: int = 0
    ) -> HealthCheckResult:
        """Execute health check command on EC2 instance via SSM.

        Args:
            ec2_client: EC2Client instance for SSM command execution
            instance_id: EC2 instance ID
            command: Command to execute (e.g., "docker ps | grep myapp")
            expected_output: Optional expected substring in output
            expected_exit_code: Expected command exit code (default: 0)

        Returns:
            HealthCheckResult with check details
        """
        logger.info(
            "Starting command health check",
            extra={"instance_id": instance_id, "command": command}
        )

        for attempt in range(1, self.max_retries + 1):
            try:
                # Execute command via SSM
                result = ec2_client.run_command(
                    instance_id=instance_id,
                    commands=[command],
                    timeout_seconds=self.timeout
                )

                exit_code = result.get("exit_code", -1)
                stdout = result.get("stdout", "")
                stderr = result.get("stderr", "")

                # Check exit code
                exit_code_match = exit_code == expected_exit_code

                # Check expected output if provided
                output_match = True
                if expected_output:
                    output_match = expected_output in stdout

                healthy = exit_code_match and output_match

                health_result = HealthCheckResult(
                    check_type="command",
                    healthy=healthy,
                    status_code=exit_code,
                    response_body=stdout[:500] if stdout else stderr[:500],
                    attempt_number=attempt,
                    max_attempts=self.max_retries
                )

                if healthy:
                    logger.info(
                        "Command health check passed",
                        extra={
                            "instance_id": instance_id,
                            "command": command,
                            "exit_code": exit_code,
                            "attempt": attempt
                        }
                    )
                    return health_result
                else:
                    error_msg = []
                    if not exit_code_match:
                        error_msg.append(f"Exit code {exit_code}, expected {expected_exit_code}")
                    if expected_output and not output_match:
                        error_msg.append(f"Output missing expected: {expected_output}")

                    health_result.error_message = "; ".join(error_msg)
                    logger.warning(
                        "Command health check failed",
                        extra={
                            "instance_id": instance_id,
                            "command": command,
                            "error": health_result.error_message,
                            "attempt": attempt
                        }
                    )

                    if attempt < self.max_retries:
                        logger.info(f"Retrying in {self.retry_delay}s...")
                        time.sleep(self.retry_delay)
                    else:
                        return health_result

            except Exception as e:
                error_message = f"Command execution failed: {str(e)}"
                logger.warning(
                    "Command health check exception",
                    extra={
                        "instance_id": instance_id,
                        "command": command,
                        "error": error_message,
                        "attempt": attempt
                    }
                )

                if attempt < self.max_retries:
                    logger.info(f"Retrying in {self.retry_delay}s...")
                    time.sleep(self.retry_delay)
                else:
                    return HealthCheckResult(
                        check_type="command",
                        healthy=False,
                        error_message=error_message,
                        attempt_number=attempt,
                        max_attempts=self.max_retries
                    )

        return HealthCheckResult(
            check_type="command",
            healthy=False,
            error_message="Max retries exceeded",
            attempt_number=self.max_retries,
            max_attempts=self.max_retries
        )
