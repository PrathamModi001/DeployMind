"""End-to-end tests for full deployment workflow.

Tests the complete deployment pipeline from GitHub repository
through security scanning, building, and deployment to EC2.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from deploymind.application.use_cases.full_deployment_workflow import (
    FullDeploymentWorkflow,
    FullDeploymentRequest,
    FullDeploymentResponse
)
from deploymind.config.settings import Settings
from deploymind.domain.entities.deployment import Deployment


@pytest.fixture
def mock_settings():
    """Create mock settings for testing."""
    settings = Mock(spec=Settings)
    settings.groq_api_key = "test_key"
    settings.github_token = "test_token"
    settings.aws_access_key_id = "test_access"
    settings.aws_secret_access_key = "test_secret"
    settings.aws_region = "us-east-1"
    settings.redis_url = "redis://localhost:6379"
    settings.database_url = "postgresql://test:test@localhost/test"
    return settings


@pytest.fixture
def mock_workflow_components():
    """Mock all workflow components."""
    with patch('application.use_cases.full_deployment_workflow.container') as mock_container, \
         patch('application.use_cases.full_deployment_workflow.RedisClient') as mock_redis_class:
        # Mock repositories
        mock_container.deployment_repo = Mock()
        mock_container.security_scan_repo = Mock()
        mock_container.build_result_repo = Mock()
        mock_container.health_check_repo = Mock()

        # Mock clients
        mock_container.github_client = Mock()
        mock_container.ec2_client = Mock()

        # Mock TrivyScanner to avoid Docker dependency
        mock_trivy = Mock()
        mock_trivy.scan_filesystem.return_value = Mock(
            passed=True,
            critical_count=0,
            high_count=0,
            vulnerabilities=[]
        )
        mock_container.trivy_scanner = mock_trivy

        # Mock RedisClient
        mock_redis_class.return_value = Mock()

        yield mock_container


class TestFullDeploymentWorkflowE2E:
    """End-to-end tests for full deployment workflow."""

    def test_successful_deployment_flow(self, mock_settings, mock_workflow_components):
        """Test complete successful deployment from start to finish."""
        # Setup: Create deployment request
        request = FullDeploymentRequest(
            repository="testuser/testapp",
            instance_id="i-1234567890abcdef",
            port=8080,
            health_check_path="/health",
            strategy="rolling",
            environment="production"
        )

        # Setup: Mock deployment tracking
        deployment_id = "test-deploy-123"
        mock_deployment = Mock(spec=Deployment)
        mock_deployment.id = deployment_id
        mock_deployment.repository = request.repository
        mock_deployment.instance_id = request.instance_id
        mock_deployment.status = "pending"

        mock_workflow_components.deployment_repo.create.return_value = mock_deployment
        mock_workflow_components.deployment_repo.get_by_id.return_value = mock_deployment

        # Setup: Mock GitHub clone
        mock_workflow_components.github_client.clone_repository.return_value = "/tmp/testapp"

        # Setup: Mock successful security scan
        mock_scan_result = Mock()
        mock_scan_result.passed = True
        mock_scan_result.critical_count = 0
        mock_scan_result.high_count = 0
        mock_scan_result.vulnerabilities = []
        mock_workflow_components.trivy_scanner.scan_filesystem.return_value = mock_scan_result

        # Setup: Mock successful Docker build
        mock_workflow_components.ec2_client.build_image.return_value = "testapp:latest"

        # Setup: Mock successful deployment
        mock_workflow_components.ec2_client.deploy_container.return_value = "container-123"

        # Setup: Mock successful health checks
        mock_workflow_components.ec2_client.run_health_checks.return_value = {
            "healthy": True,
            "checks_passed": 12,
            "checks_failed": 0,
            "details": []
        }

        # Execute: Run workflow
        workflow = FullDeploymentWorkflow(mock_settings)
        response = workflow.execute(request)

        # Assert: Workflow completed successfully
        assert response.success is True
        assert response.deployment_id == deployment_id
        assert response.image_tag is not None
        assert response.error_message is None
        assert response.rollback_performed is False

        # Assert: All phases were executed
        mock_workflow_components.github_client.clone_repository.assert_called_once()
        mock_workflow_components.trivy_scanner.scan_filesystem.assert_called_once()
        mock_workflow_components.ec2_client.build_image.assert_called_once()
        mock_workflow_components.ec2_client.deploy_container.assert_called_once()
        mock_workflow_components.ec2_client.run_health_checks.assert_called_once()

    def test_deployment_fails_at_security_scan(self, mock_settings, mock_workflow_components):
        """Test deployment fails gracefully when security scan fails."""
        request = FullDeploymentRequest(
            repository="testuser/testapp",
            instance_id="i-1234567890abcdef",
            port=8080
        )

        deployment_id = "test-deploy-456"
        mock_deployment = Mock(spec=Deployment)
        mock_deployment.id = deployment_id

        mock_workflow_components.deployment_repo.create.return_value = mock_deployment
        mock_workflow_components.deployment_repo.get_by_id.return_value = mock_deployment
        mock_workflow_components.github_client.clone_repository.return_value = "/tmp/testapp"

        # Setup: Mock failed security scan
        mock_scan_result = Mock()
        mock_scan_result.passed = False
        mock_scan_result.critical_count = 5
        mock_scan_result.high_count = 10
        mock_scan_result.vulnerabilities = [{"severity": "CRITICAL", "cve": "CVE-2024-0001"}]
        mock_workflow_components.trivy_scanner.scan_filesystem.return_value = mock_scan_result

        # Execute
        workflow = FullDeploymentWorkflow(mock_settings)
        response = workflow.execute(request)

        # Assert: Deployment failed at security scan
        assert response.success is False
        assert response.error_message is not None
        assert "security" in response.error_message.lower() or "vulnerabilities" in response.error_message.lower()

        # Assert: Build and deploy were NOT called
        mock_workflow_components.ec2_client.build_image.assert_not_called()
        mock_workflow_components.ec2_client.deploy_container.assert_not_called()

    def test_deployment_fails_at_build(self, mock_settings, mock_workflow_components):
        """Test deployment fails gracefully when Docker build fails."""
        request = FullDeploymentRequest(
            repository="testuser/testapp",
            instance_id="i-1234567890abcdef",
            port=8080
        )

        deployment_id = "test-deploy-789"
        mock_deployment = Mock(spec=Deployment)
        mock_deployment.id = deployment_id

        mock_workflow_components.deployment_repo.create.return_value = mock_deployment
        mock_workflow_components.deployment_repo.get_by_id.return_value = mock_deployment
        mock_workflow_components.github_client.clone_repository.return_value = "/tmp/testapp"

        # Setup: Mock successful security scan
        mock_scan_result = Mock()
        mock_scan_result.passed = True
        mock_scan_result.critical_count = 0
        mock_workflow_components.trivy_scanner.scan_filesystem.return_value = mock_scan_result

        # Setup: Mock failed Docker build
        mock_workflow_components.ec2_client.build_image.side_effect = Exception("Docker build failed: Invalid Dockerfile")

        # Execute
        workflow = FullDeploymentWorkflow(mock_settings)
        response = workflow.execute(request)

        # Assert: Deployment failed at build
        assert response.success is False
        assert response.error_message is not None
        assert "build" in response.error_message.lower() or "docker" in response.error_message.lower()

        # Assert: Deploy was NOT called
        mock_workflow_components.ec2_client.deploy_container.assert_not_called()

    def test_deployment_with_health_check_failure_triggers_rollback(self, mock_settings, mock_workflow_components):
        """Test deployment triggers rollback when health checks fail."""
        request = FullDeploymentRequest(
            repository="testuser/testapp",
            instance_id="i-1234567890abcdef",
            port=8080,
            health_check_path="/health"
        )

        deployment_id = "test-deploy-999"
        mock_deployment = Mock(spec=Deployment)
        mock_deployment.id = deployment_id

        mock_workflow_components.deployment_repo.create.return_value = mock_deployment
        mock_workflow_components.deployment_repo.get_by_id.return_value = mock_deployment
        mock_workflow_components.github_client.clone_repository.return_value = "/tmp/testapp"

        # Setup: Mock successful security scan and build
        mock_scan_result = Mock()
        mock_scan_result.passed = True
        mock_scan_result.critical_count = 0
        mock_workflow_components.trivy_scanner.scan_filesystem.return_value = mock_scan_result
        mock_workflow_components.ec2_client.build_image.return_value = "testapp:latest"
        mock_workflow_components.ec2_client.deploy_container.return_value = "container-456"

        # Setup: Mock failed health checks
        mock_workflow_components.ec2_client.run_health_checks.return_value = {
            "healthy": False,
            "checks_passed": 3,
            "checks_failed": 9,
            "details": [{"check": "http", "status": "failed", "error": "Connection refused"}]
        }

        # Setup: Mock rollback
        mock_workflow_components.ec2_client.rollback_deployment.return_value = True

        # Execute
        workflow = FullDeploymentWorkflow(mock_settings)
        response = workflow.execute(request)

        # Assert: Deployment failed and rollback occurred
        assert response.success is False
        assert response.rollback_performed is True
        assert response.error_message is not None
        assert "health" in response.error_message.lower()

        # Assert: Rollback was called
        mock_workflow_components.ec2_client.rollback_deployment.assert_called_once()

    def test_deployment_with_multiple_repositories(self, mock_settings, mock_workflow_components):
        """Test deploying multiple different repositories in sequence."""
        repositories = ["user/app1", "user/app2", "user/app3"]

        for idx, repo in enumerate(repositories):
            request = FullDeploymentRequest(
                repository=repo,
                instance_id=f"i-test{idx}",
                port=8080 + idx
            )

            deployment_id = f"test-deploy-multi-{idx}"
            mock_deployment = Mock(spec=Deployment)
            mock_deployment.id = deployment_id
            mock_deployment.repository = repo

            mock_workflow_components.deployment_repo.create.return_value = mock_deployment
            mock_workflow_components.deployment_repo.get_by_id.return_value = mock_deployment
            mock_workflow_components.github_client.clone_repository.return_value = f"/tmp/{repo.split('/')[1]}"

            # Mock successful flow
            mock_scan_result = Mock()
            mock_scan_result.passed = True
            mock_scan_result.critical_count = 0
            mock_workflow_components.trivy_scanner.scan_filesystem.return_value = mock_scan_result
            mock_workflow_components.ec2_client.build_image.return_value = f"{repo.split('/')[1]}:latest"
            mock_workflow_components.ec2_client.deploy_container.return_value = f"container-{idx}"
            mock_workflow_components.ec2_client.run_health_checks.return_value = {
                "healthy": True,
                "checks_passed": 12,
                "checks_failed": 0
            }

            # Execute
            workflow = FullDeploymentWorkflow(mock_settings)
            response = workflow.execute(request)

            # Assert: Each deployment succeeds
            assert response.success is True
            assert response.deployment_id == deployment_id

    @pytest.mark.parametrize("strategy", ["rolling", "blue-green", "canary"])
    def test_deployment_with_different_strategies(self, strategy, mock_settings, mock_workflow_components):
        """Test deployment works with different deployment strategies."""
        request = FullDeploymentRequest(
            repository="testuser/testapp",
            instance_id="i-1234567890abcdef",
            port=8080,
            strategy=strategy
        )

        deployment_id = f"test-deploy-{strategy}"
        mock_deployment = Mock(spec=Deployment)
        mock_deployment.id = deployment_id
        mock_deployment.strategy = strategy

        mock_workflow_components.deployment_repo.create.return_value = mock_deployment
        mock_workflow_components.deployment_repo.get_by_id.return_value = mock_deployment
        mock_workflow_components.github_client.clone_repository.return_value = "/tmp/testapp"

        # Mock successful flow
        mock_scan_result = Mock()
        mock_scan_result.passed = True
        mock_scan_result.critical_count = 0
        mock_workflow_components.trivy_scanner.scan_filesystem.return_value = mock_scan_result
        mock_workflow_components.ec2_client.build_image.return_value = "testapp:latest"
        mock_workflow_components.ec2_client.deploy_container.return_value = "container-123"
        mock_workflow_components.ec2_client.run_health_checks.return_value = {
            "healthy": True,
            "checks_passed": 12,
            "checks_failed": 0
        }

        # Execute
        workflow = FullDeploymentWorkflow(mock_settings)
        response = workflow.execute(request)

        # Assert: Deployment succeeds with specified strategy
        assert response.success is True
        assert mock_deployment.strategy == strategy

    @pytest.mark.parametrize("environment", ["development", "staging", "production"])
    def test_deployment_to_different_environments(self, environment, mock_settings, mock_workflow_components):
        """Test deployment works across different environments."""
        request = FullDeploymentRequest(
            repository="testuser/testapp",
            instance_id="i-1234567890abcdef",
            port=8080,
            environment=environment
        )

        deployment_id = f"test-deploy-{environment}"
        mock_deployment = Mock(spec=Deployment)
        mock_deployment.id = deployment_id

        mock_workflow_components.deployment_repo.create.return_value = mock_deployment
        mock_workflow_components.deployment_repo.get_by_id.return_value = mock_deployment
        mock_workflow_components.github_client.clone_repository.return_value = "/tmp/testapp"

        # Mock successful flow
        mock_scan_result = Mock()
        mock_scan_result.passed = True
        mock_scan_result.critical_count = 0
        mock_workflow_components.trivy_scanner.scan_filesystem.return_value = mock_scan_result
        mock_workflow_components.ec2_client.build_image.return_value = "testapp:latest"
        mock_workflow_components.ec2_client.deploy_container.return_value = "container-123"
        mock_workflow_components.ec2_client.run_health_checks.return_value = {
            "healthy": True,
            "checks_passed": 12,
            "checks_failed": 0
        }

        # Execute
        workflow = FullDeploymentWorkflow(mock_settings)
        response = workflow.execute(request)

        # Assert: Deployment succeeds in specified environment
        assert response.success is True
        assert response.deployment_id == deployment_id


class TestDeploymentPersistenceE2E:
    """Test deployment data persistence throughout the workflow."""

    def test_deployment_status_transitions(self, mock_settings, mock_workflow_components):
        """Test deployment status transitions through workflow phases."""
        request = FullDeploymentRequest(
            repository="testuser/testapp",
            instance_id="i-1234567890abcdef",
            port=8080
        )

        deployment_id = "test-status-transitions"
        mock_deployment = Mock(spec=Deployment)
        mock_deployment.id = deployment_id
        mock_deployment.status = "pending"

        status_updates = []

        def track_status_update(deployment_id, **kwargs):
            if 'status' in kwargs:
                status_updates.append(kwargs['status'])
            return mock_deployment

        mock_workflow_components.deployment_repo.create.return_value = mock_deployment
        mock_workflow_components.deployment_repo.get_by_id.return_value = mock_deployment
        mock_workflow_components.deployment_repo.update.side_effect = track_status_update
        mock_workflow_components.github_client.clone_repository.return_value = "/tmp/testapp"

        # Mock successful flow
        mock_scan_result = Mock()
        mock_scan_result.passed = True
        mock_scan_result.critical_count = 0
        mock_workflow_components.trivy_scanner.scan_filesystem.return_value = mock_scan_result
        mock_workflow_components.ec2_client.build_image.return_value = "testapp:latest"
        mock_workflow_components.ec2_client.deploy_container.return_value = "container-123"
        mock_workflow_components.ec2_client.run_health_checks.return_value = {
            "healthy": True,
            "checks_passed": 12,
            "checks_failed": 0
        }

        # Execute
        workflow = FullDeploymentWorkflow(mock_settings)
        response = workflow.execute(request)

        # Assert: Status transitions occurred
        assert response.success is True
        # Verify status progressed through expected phases
        assert len(status_updates) > 0

    def test_security_scan_results_persisted(self, mock_settings, mock_workflow_components):
        """Test security scan results are persisted to database."""
        request = FullDeploymentRequest(
            repository="testuser/testapp",
            instance_id="i-1234567890abcdef",
            port=8080
        )

        deployment_id = "test-security-persist"
        mock_deployment = Mock(spec=Deployment)
        mock_deployment.id = deployment_id

        mock_workflow_components.deployment_repo.create.return_value = mock_deployment
        mock_workflow_components.deployment_repo.get_by_id.return_value = mock_deployment
        mock_workflow_components.github_client.clone_repository.return_value = "/tmp/testapp"

        # Mock security scan with vulnerabilities
        mock_scan_result = Mock()
        mock_scan_result.passed = True
        mock_scan_result.critical_count = 0
        mock_scan_result.high_count = 2
        mock_scan_result.medium_count = 5
        mock_scan_result.vulnerabilities = [
            {"severity": "HIGH", "cve": "CVE-2024-0001"},
            {"severity": "MEDIUM", "cve": "CVE-2024-0002"}
        ]
        mock_workflow_components.trivy_scanner.scan_filesystem.return_value = mock_scan_result
        mock_workflow_components.ec2_client.build_image.return_value = "testapp:latest"
        mock_workflow_components.ec2_client.deploy_container.return_value = "container-123"
        mock_workflow_components.ec2_client.run_health_checks.return_value = {
            "healthy": True,
            "checks_passed": 12,
            "checks_failed": 0
        }

        # Execute
        workflow = FullDeploymentWorkflow(mock_settings)
        response = workflow.execute(request)

        # Assert: Security scan was persisted
        assert response.success is True
        mock_workflow_components.security_scan_repo.create.assert_called()

    def test_build_results_persisted(self, mock_settings, mock_workflow_components):
        """Test build results are persisted to database."""
        request = FullDeploymentRequest(
            repository="testuser/testapp",
            instance_id="i-1234567890abcdef",
            port=8080
        )

        deployment_id = "test-build-persist"
        mock_deployment = Mock(spec=Deployment)
        mock_deployment.id = deployment_id

        mock_workflow_components.deployment_repo.create.return_value = mock_deployment
        mock_workflow_components.deployment_repo.get_by_id.return_value = mock_deployment
        mock_workflow_components.github_client.clone_repository.return_value = "/tmp/testapp"

        # Mock successful flow
        mock_scan_result = Mock()
        mock_scan_result.passed = True
        mock_scan_result.critical_count = 0
        mock_workflow_components.trivy_scanner.scan_filesystem.return_value = mock_scan_result
        mock_workflow_components.ec2_client.build_image.return_value = "testapp:v1.2.3"
        mock_workflow_components.ec2_client.deploy_container.return_value = "container-123"
        mock_workflow_components.ec2_client.run_health_checks.return_value = {
            "healthy": True,
            "checks_passed": 12,
            "checks_failed": 0
        }

        # Execute
        workflow = FullDeploymentWorkflow(mock_settings)
        response = workflow.execute(request)

        # Assert: Build result was persisted
        assert response.success is True
        assert response.image_tag == "testapp:v1.2.3"
        mock_workflow_components.build_result_repo.create.assert_called()

    def test_health_check_results_persisted(self, mock_settings, mock_workflow_components):
        """Test health check results are persisted to database."""
        request = FullDeploymentRequest(
            repository="testuser/testapp",
            instance_id="i-1234567890abcdef",
            port=8080,
            health_check_path="/health"
        )

        deployment_id = "test-health-persist"
        mock_deployment = Mock(spec=Deployment)
        mock_deployment.id = deployment_id

        mock_workflow_components.deployment_repo.create.return_value = mock_deployment
        mock_workflow_components.deployment_repo.get_by_id.return_value = mock_deployment
        mock_workflow_components.github_client.clone_repository.return_value = "/tmp/testapp"

        # Mock successful flow
        mock_scan_result = Mock()
        mock_scan_result.passed = True
        mock_scan_result.critical_count = 0
        mock_workflow_components.trivy_scanner.scan_filesystem.return_value = mock_scan_result
        mock_workflow_components.ec2_client.build_image.return_value = "testapp:latest"
        mock_workflow_components.ec2_client.deploy_container.return_value = "container-123"
        mock_workflow_components.ec2_client.run_health_checks.return_value = {
            "healthy": True,
            "checks_passed": 12,
            "checks_failed": 0,
            "details": [
                {"check": "http", "status": "passed"},
                {"check": "process", "status": "passed"}
            ]
        }

        # Execute
        workflow = FullDeploymentWorkflow(mock_settings)
        response = workflow.execute(request)

        # Assert: Health checks were persisted
        assert response.success is True
        mock_workflow_components.health_check_repo.create.assert_called()
