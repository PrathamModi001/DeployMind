"""Comprehensive tests for Day 4: Deploy Agent implementation.

Tests cover:
- HealthChecker (HTTP, TCP, command checks)
- EC2Client deployment operations
- RollingDeployer (deployment, rollback)
- DeployApplicationUseCase
- Deploy Agent tools
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

# Infrastructure components
from deploymind.infrastructure.monitoring.health_checker import HealthChecker, HealthCheckResult
from deploymind.infrastructure.deployment.rolling_deployer import RollingDeployer, DeploymentResult
from deploymind.infrastructure.cloud.aws.ec2_client import EC2Client

# Application layer
from deploymind.application.use_cases.deploy_application import (
    DeployApplicationUseCase,
    DeployRequest,
    DeployResponse
)

# Config and shared
from deploymind.config.settings import Settings
from deploymind.shared.exceptions import ValidationError, DeploymentError


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def mock_settings():
    """Mock Settings with test credentials."""
    settings = Mock(spec=Settings)
    settings.aws_access_key_id = "test_key"
    settings.aws_secret_access_key = "test_secret"
    settings.aws_region = "us-east-1"
    settings.groq_api_key = "test_groq_key"
    return settings


@pytest.fixture
def mock_ec2_client(mock_settings):
    """Mock EC2Client."""
    return Mock(spec=EC2Client)


@pytest.fixture
def health_checker():
    """Create HealthChecker instance."""
    return HealthChecker(timeout=5, max_retries=2, retry_delay=1)


@pytest.fixture
def rolling_deployer(mock_ec2_client):
    """Create RollingDeployer with mocked EC2Client."""
    health_checker = Mock(spec=HealthChecker)
    return RollingDeployer(
        ec2_client=mock_ec2_client,
        health_checker=health_checker,
        health_check_duration=30,
        health_check_interval=10
    )


@pytest.fixture
def deploy_use_case(mock_settings):
    """Create DeployApplicationUseCase with mocked dependencies."""
    use_case = DeployApplicationUseCase(mock_settings)
    use_case.rolling_deployer = Mock(spec=RollingDeployer)
    return use_case


# =============================================================================
# TEST HEALTH CHECKER
# =============================================================================

class TestHealthChecker:
    """Test HealthChecker functionality."""

    @patch('deploymind.infrastructure.monitoring.health_checker.requests.get')
    def test_http_check_success(self, mock_get, health_checker):
        """Test successful HTTP health check."""
        # Mock successful HTTP response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = '{"status": "healthy"}'
        mock_get.return_value = mock_response

        result = health_checker.check_http("http://example.com:8080/health")

        assert result.healthy is True
        assert result.check_type == "http"
        assert result.status_code == 200
        assert result.response_time_ms is not None

    @patch('deploymind.infrastructure.monitoring.health_checker.requests.get')
    def test_http_check_failure(self, mock_get, health_checker):
        """Test HTTP health check failure."""
        # Mock failed HTTP response
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.text = 'Internal Server Error'
        mock_get.return_value = mock_response

        result = health_checker.check_http("http://example.com:8080/health")

        assert result.healthy is False
        assert result.status_code == 500
        assert result.error_message is not None

    @patch('deploymind.infrastructure.monitoring.health_checker.requests.get')
    def test_http_check_timeout(self, mock_get, health_checker):
        """Test HTTP health check timeout."""
        import requests
        mock_get.side_effect = requests.exceptions.Timeout("Connection timeout")

        result = health_checker.check_http("http://example.com:8080/health")

        assert result.healthy is False
        assert result.error_message is not None
        assert "timeout" in result.error_message.lower()

    @patch('deploymind.infrastructure.monitoring.health_checker.socket.socket')
    def test_tcp_check_success(self, mock_socket, health_checker):
        """Test successful TCP port check."""
        # Mock successful TCP connection
        mock_sock = Mock()
        mock_sock.connect_ex.return_value = 0  # Success
        mock_socket.return_value = mock_sock

        result = health_checker.check_tcp("example.com", 8080)

        assert result.healthy is True
        assert result.check_type == "tcp"
        assert result.response_time_ms is not None

    @patch('deploymind.infrastructure.monitoring.health_checker.socket.socket')
    def test_tcp_check_failure(self, mock_socket, health_checker):
        """Test TCP port check failure."""
        # Mock failed TCP connection
        mock_sock = Mock()
        mock_sock.connect_ex.return_value = 1  # Connection refused
        mock_socket.return_value = mock_sock

        result = health_checker.check_tcp("example.com", 8080)

        assert result.healthy is False
        assert result.error_message is not None

    def test_command_check_success(self, health_checker):
        """Test successful command health check."""
        # Mock EC2 client
        mock_ec2 = Mock()
        mock_ec2.run_command.return_value = {
            "exit_code": 0,
            "stdout": "container running",
            "stderr": ""
        }

        result = health_checker.check_command(
            ec2_client=mock_ec2,
            instance_id="i-1234567890abcdef0",
            command="docker ps | grep myapp"
        )

        assert result.healthy is True
        assert result.check_type == "command"
        assert result.status_code == 0

    def test_command_check_failure(self, health_checker):
        """Test command health check failure."""
        # Mock EC2 client with failed command
        mock_ec2 = Mock()
        mock_ec2.run_command.return_value = {
            "exit_code": 1,
            "stdout": "",
            "stderr": "container not found"
        }

        result = health_checker.check_command(
            ec2_client=mock_ec2,
            instance_id="i-1234567890abcdef0",
            command="docker ps | grep myapp"
        )

        assert result.healthy is False
        assert result.status_code == 1
        assert result.error_message is not None


# =============================================================================
# TEST EC2 CLIENT DEPLOYMENT OPERATIONS
# =============================================================================

class TestEC2ClientDeployment:
    """Test EC2Client deployment-specific operations."""

    @patch.object(EC2Client, 'run_command')
    @patch.object(EC2Client, 'get_container_status')
    def test_deploy_container_success(self, mock_status, mock_run, mock_ec2_client, mock_settings):
        """Test successful container deployment."""
        # Create real EC2Client for testing
        ec2_client = EC2Client(mock_settings)

        # Mock docker pull
        mock_run.side_effect = [
            {"exit_code": 0, "stdout": "Pull complete", "stderr": ""},
            {"exit_code": 0, "stdout": "", "stderr": ""},  # stop
            {"exit_code": 0, "stdout": "", "stderr": ""},  # rm
            {"exit_code": 0, "stdout": "abc123def456", "stderr": ""}  # run
        ]

        # Mock container status
        mock_status.return_value = {
            "running": True,
            "status": "running",
            "container_id": "abc123def456"
        }

        # Mock get_instance_public_ip (needed for internal checks)
        with patch.object(ec2_client, 'get_instance_public_ip', return_value="1.2.3.4"):
            result = ec2_client.deploy_container(
                instance_id="i-1234567890abcdef0",
                image_tag="myapp:v1.0",
                port=8080
            )

        assert result["container_id"] == "abc123def456"
        assert result["running"] is True
        assert result["image_tag"] == "myapp:v1.0"

    @patch.object(EC2Client, 'run_command')
    def test_pull_docker_image(self, mock_run, mock_ec2_client, mock_settings):
        """Test Docker image pull."""
        ec2_client = EC2Client(mock_settings)

        mock_run.return_value = {
            "exit_code": 0,
            "stdout": "latest: Pulling from myrepo/myapp\\nPull complete",
            "stderr": ""
        }

        result = ec2_client.pull_docker_image("i-1234567890abcdef0", "myapp:latest")

        assert result["exit_code"] == 0
        mock_run.assert_called_once()

    @patch.object(EC2Client, 'run_command')
    def test_stop_container(self, mock_run, mock_ec2_client, mock_settings):
        """Test container stop operation."""
        ec2_client = EC2Client(mock_settings)

        mock_run.return_value = {
            "exit_code": 0,
            "stdout": "myapp",
            "stderr": ""
        }

        result = ec2_client.stop_container(
            instance_id="i-1234567890abcdef0",
            container_name="myapp"
        )

        assert result["exit_code"] == 0
        assert mock_run.call_count == 2  # stop + rm

    @patch.object(EC2Client, 'run_command')
    def test_get_container_status(self, mock_run, mock_ec2_client, mock_settings):
        """Test get container status."""
        ec2_client = EC2Client(mock_settings)

        # Mock docker inspect command
        mock_run.side_effect = [
            {"exit_code": 0, "stdout": "running", "stderr": ""},
            {"exit_code": 0, "stdout": "abc123", "stderr": ""},
            {"exit_code": 0, "stdout": "2026-02-06T10:00:00Z", "stderr": ""}
        ]

        status = ec2_client.get_container_status("i-1234567890abcdef0", "myapp")

        assert status["running"] is True
        assert status["status"] == "running"
        assert status["container_id"] == "abc123"


# =============================================================================
# TEST ROLLING DEPLOYER
# =============================================================================

class TestRollingDeployer:
    """Test RollingDeployer functionality."""

    def test_deploy_success(self, rolling_deployer, mock_ec2_client):
        """Test successful rolling deployment."""
        # Mock EC2Client methods
        mock_ec2_client.get_instance_public_ip.return_value = "1.2.3.4"
        mock_ec2_client.check_ssm_agent_status.return_value = True

        # Mock container status for old container and 3 health check iterations
        mock_ec2_client.get_container_status.side_effect = [
            {"running": True, "status": "running"},  # Old container before deployment
            {"running": True, "status": "running"},  # Check 1
            {"running": True, "status": "running"},  # Check 2
            {"running": True, "status": "running"}   # Check 3
        ]

        mock_ec2_client.deploy_container.return_value = {
            "container_id": "new123",
            "container_name": "app",
            "running": True
        }

        # Mock health checker - return HealthCheckResult for each call
        def create_health_result():
            return HealthCheckResult(
                check_type="http",
                healthy=True,
                status_code=200,
                response_time_ms=50
            )

        rolling_deployer.health_checker.check_http.side_effect = [
            create_health_result(),
            create_health_result(),
            create_health_result()
        ]

        # Execute deployment
        result = rolling_deployer.deploy(
            deployment_id="deploy-001",
            instance_id="i-1234567890abcdef0",
            image_tag="myapp:v2.0",
            port=8080
        )

        assert result.success is True
        assert result.container_id == "new123"
        assert result.health_check_result is not None
        assert result.health_check_result.healthy is True

    def test_deploy_health_check_failure_with_rollback(self, rolling_deployer, mock_ec2_client):
        """Test deployment with health check failure triggers rollback."""
        # Mock EC2Client methods
        mock_ec2_client.get_instance_public_ip.return_value = "1.2.3.4"
        mock_ec2_client.check_ssm_agent_status.return_value = True
        mock_ec2_client.get_container_status.return_value = {
            "running": True,
            "status": "running"
        }
        mock_ec2_client.deploy_container.return_value = {
            "container_id": "new123",
            "container_name": "app",
            "running": True
        }

        # Mock health checker - FAILURE
        rolling_deployer.health_checker.check_http.return_value = HealthCheckResult(
            check_type="http",
            healthy=False,
            status_code=500,
            error_message="Service unavailable"
        )

        # Execute deployment
        result = rolling_deployer.deploy(
            deployment_id="deploy-002",
            instance_id="i-1234567890abcdef0",
            image_tag="myapp:v2.0-broken",
            port=8080,
            previous_image_tag="myapp:v1.0"
        )

        assert result.success is False
        assert result.rollback_performed is True
        assert "Health checks failed" in result.error_message

    def test_rollback_manually(self, rolling_deployer, mock_ec2_client):
        """Test manual rollback operation."""
        # Mock EC2Client methods
        mock_ec2_client.stop_container.return_value = {"exit_code": 0}
        mock_ec2_client.deploy_container.return_value = {
            "container_id": "old123",
            "running": True
        }

        result = rolling_deployer.rollback(
            deployment_id="deploy-003",
            instance_id="i-1234567890abcdef0",
            container_name="app",
            previous_image_tag="myapp:v1.0",
            port=8080
        )

        assert result.success is True
        assert result.rollback_performed is True
        assert result.image_tag == "myapp:v1.0"


# =============================================================================
# TEST DEPLOY APPLICATION USE CASE
# =============================================================================

class TestDeployApplicationUseCase:
    """Test DeployApplicationUseCase."""

    def test_execute_success(self, deploy_use_case):
        """Test successful deployment execution."""
        # Mock rolling deployer result
        deploy_use_case.rolling_deployer.deploy.return_value = DeploymentResult(
            success=True,
            deployment_id="deploy-004",
            instance_id="i-1234567890abcdef0",
            image_tag="myapp:v1.0",
            container_id="abc123",
            health_check_result=HealthCheckResult(
                check_type="http",
                healthy=True,
                status_code=200,
                response_time_ms=50
            ),
            deployment_duration_seconds=150
        )

        # Create request
        request = DeployRequest(
            deployment_id="deploy-004",
            instance_id="i-1234567890abcdef0",
            image_tag="myapp:v1.0",
            port=8080
        )

        # Execute
        response = deploy_use_case.execute(request)

        assert response.success is True
        assert response.deployment_id == "deploy-004"
        assert response.container_id == "abc123"
        assert response.health_check_passed is True

    def test_validate_request_invalid_instance_id(self, deploy_use_case):
        """Test validation failure for invalid instance ID."""
        request = DeployRequest(
            deployment_id="deploy-005",
            instance_id="invalid-instance",
            image_tag="myapp:v1.0"
        )

        with pytest.raises(ValidationError) as exc_info:
            deploy_use_case._validate_request(request)

        assert "Invalid instance ID format" in str(exc_info.value)

    def test_validate_request_invalid_port(self, deploy_use_case):
        """Test validation failure for invalid port."""
        request = DeployRequest(
            deployment_id="deploy-006",
            instance_id="i-1234567890abcdef0",
            image_tag="myapp:v1.0",
            port=99999  # Invalid
        )

        with pytest.raises(ValidationError) as exc_info:
            deploy_use_case._validate_request(request)

        assert "Invalid port number" in str(exc_info.value)

    def test_validate_request_invalid_health_check_path(self, deploy_use_case):
        """Test validation failure for invalid health check path."""
        request = DeployRequest(
            deployment_id="deploy-007",
            instance_id="i-1234567890abcdef0",
            image_tag="myapp:v1.0",
            health_check_path="health"  # Missing leading /
        )

        with pytest.raises(ValidationError) as exc_info:
            deploy_use_case._validate_request(request)

        assert "Health check path must start with /" in str(exc_info.value)


# =============================================================================
# RUN TESTS
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
