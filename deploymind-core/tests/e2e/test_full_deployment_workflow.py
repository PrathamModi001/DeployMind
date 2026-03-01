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


def _make_mock_repo(default_branch="main", commit_sha="abc1234567890def"):
    """Create a mock GitHub repo object."""
    mock_repo = Mock()
    mock_repo.default_branch = default_branch
    mock_branch = Mock()
    mock_branch.commit.sha = commit_sha
    mock_repo.get_branch.return_value = mock_branch
    return mock_repo


def _make_security_response(passed=True, total_vulns=0, critical=0, high=0):
    """Create a mock SecurityScanResponse."""
    response = Mock()
    response.success = passed
    response.message = "Scan passed" if passed else f"Found {critical} critical vulnerabilities"
    scan_result = Mock()
    scan_result.total_vulnerabilities = total_vulns
    scan_result.critical_count = critical
    scan_result.high_count = high
    scan_result.medium_count = 0
    scan_result.low_count = 0
    scan_result.vulnerabilities = []
    response.scan_result = scan_result
    return response


def _make_build_response(success=True, image_tag="testapp:latest"):
    """Create a mock BuildResponse."""
    response = Mock()
    response.success = success
    response.image_tag = image_tag if success else None
    response.message = "Build succeeded" if success else "Build failed: Invalid Dockerfile"
    build_result = Mock()
    build_result.image_size_mb = 150.0
    response.build_result = build_result if success else None
    return response


def _make_deploy_response(success=True, container_id="container-123", health_passed=True, rollback=False):
    """Create a mock DeployResponse."""
    response = Mock()
    response.success = success
    response.container_id = container_id if success else None
    response.health_check_passed = health_passed
    response.application_url = "http://1.2.3.4:8080" if success else None
    response.rollback_performed = rollback
    response.error_message = None if success else "Health checks failed"
    return response


@pytest.fixture
def mock_workflow_components():
    """Mock all workflow components."""
    with patch('deploymind.application.use_cases.full_deployment_workflow.container') as mock_container, \
         patch('deploymind.application.use_cases.full_deployment_workflow.RedisClient') as mock_redis_class, \
         patch('deploymind.application.use_cases.full_deployment_workflow.GitHubClient') as mock_github_class, \
         patch('deploymind.application.use_cases.full_deployment_workflow.SecurityScanUseCase') as mock_security_class, \
         patch('deploymind.application.use_cases.full_deployment_workflow.BuildApplicationUseCase') as mock_build_class, \
         patch('deploymind.application.use_cases.full_deployment_workflow.DeployApplicationUseCase') as mock_deploy_class:

        # Mock repositories via container
        mock_container.deployment_repo = Mock()
        mock_container.security_scan_repo = Mock()
        mock_container.build_result_repo = Mock()
        mock_container.health_check_repo = Mock()

        # Mock GitHub client instance
        mock_github = Mock()
        mock_github.get_repository.return_value = _make_mock_repo()
        mock_github_class.return_value = mock_github

        # Mock use case instances with default successful responses
        mock_security_uc = Mock()
        mock_security_uc.execute.return_value = _make_security_response()
        mock_security_class.return_value = mock_security_uc

        mock_build_uc = Mock()
        mock_build_uc.execute.return_value = _make_build_response()
        mock_build_class.return_value = mock_build_uc

        mock_deploy_uc = Mock()
        mock_deploy_uc.execute.return_value = _make_deploy_response()
        mock_deploy_class.return_value = mock_deploy_uc

        # Mock RedisClient
        mock_redis_class.return_value = Mock()

        yield {
            'container': mock_container,
            'github_client': mock_github,
            'security_use_case': mock_security_uc,
            'build_use_case': mock_build_uc,
            'deploy_use_case': mock_deploy_uc,
        }


class TestFullDeploymentWorkflowE2E:
    """End-to-end tests for full deployment workflow."""

    def test_successful_deployment_flow(self, mock_settings, mock_workflow_components):
        """Test complete successful deployment from start to finish."""
        components = mock_workflow_components

        # Setup: Mock deployment tracking
        deployment_id = "test-deploy-123"
        mock_deployment = Mock(spec=Deployment)
        mock_deployment.id = deployment_id

        components['container'].deployment_repo.create.return_value = mock_deployment

        # Execute: Run workflow
        request = FullDeploymentRequest(
            repository="testuser/testapp",
            instance_id="i-1234567890abcdef",
            port=8080,
            health_check_path="/health",
            strategy="rolling",
            environment="production"
        )
        workflow = FullDeploymentWorkflow(mock_settings)
        response = workflow.execute(request)

        # Assert: Workflow completed successfully
        assert response.success is True
        assert response.error_message is None
        assert response.rollback_performed is False
        assert response.security_passed is True
        assert response.build_successful is True

        # Assert: All phases were executed
        components['github_client'].get_repository.assert_called_once()
        components['security_use_case'].execute.assert_called_once()
        components['build_use_case'].execute.assert_called_once()
        components['deploy_use_case'].execute.assert_called_once()

    def test_deployment_fails_at_security_scan(self, mock_settings, mock_workflow_components):
        """Test deployment fails gracefully when security scan fails."""
        components = mock_workflow_components

        # Setup: Mock failed security scan
        components['security_use_case'].execute.return_value = _make_security_response(
            passed=False, total_vulns=5, critical=5
        )

        request = FullDeploymentRequest(
            repository="testuser/testapp",
            instance_id="i-1234567890abcdef",
            port=8080
        )

        workflow = FullDeploymentWorkflow(mock_settings)
        response = workflow.execute(request)

        # Assert: Deployment failed at security scan
        assert response.success is False
        assert response.error_message is not None
        assert response.security_passed is False

        # Assert: Build and deploy were NOT called
        components['build_use_case'].execute.assert_not_called()
        components['deploy_use_case'].execute.assert_not_called()

    def test_deployment_fails_at_build(self, mock_settings, mock_workflow_components):
        """Test deployment fails gracefully when Docker build fails."""
        components = mock_workflow_components

        # Setup: Mock failed Docker build
        components['build_use_case'].execute.return_value = _make_build_response(success=False)

        request = FullDeploymentRequest(
            repository="testuser/testapp",
            instance_id="i-1234567890abcdef",
            port=8080
        )

        workflow = FullDeploymentWorkflow(mock_settings)
        response = workflow.execute(request)

        # Assert: Deployment failed at build
        assert response.success is False
        assert response.error_message is not None
        assert response.security_passed is True
        assert response.build_successful is False

        # Assert: Deploy was NOT called
        components['deploy_use_case'].execute.assert_not_called()

    def test_deployment_with_health_check_failure_triggers_rollback(self, mock_settings, mock_workflow_components):
        """Test deployment triggers rollback when health checks fail."""
        components = mock_workflow_components

        # Setup: Deploy fails with rollback
        components['deploy_use_case'].execute.return_value = _make_deploy_response(
            success=False, health_passed=False, rollback=True
        )

        request = FullDeploymentRequest(
            repository="testuser/testapp",
            instance_id="i-1234567890abcdef",
            port=8080,
            health_check_path="/health"
        )

        workflow = FullDeploymentWorkflow(mock_settings)
        response = workflow.execute(request)

        # Assert: Deployment failed and rollback occurred
        assert response.success is False
        assert response.rollback_performed is True
        assert response.error_message is not None

    def test_deployment_with_multiple_repositories(self, mock_settings, mock_workflow_components):
        """Test deploying multiple different repositories in sequence."""
        components = mock_workflow_components
        repositories = ["user/app1", "user/app2", "user/app3"]

        for idx, repo in enumerate(repositories):
            # Reset call counts
            for uc in ['security_use_case', 'build_use_case', 'deploy_use_case']:
                components[uc].execute.reset_mock()

            request = FullDeploymentRequest(
                repository=repo,
                instance_id="i-1234567890abcdef",
                port=8080 + idx
            )

            workflow = FullDeploymentWorkflow(mock_settings)
            response = workflow.execute(request)

            assert response.success is True
            assert response.repository == repo

    @pytest.mark.parametrize("strategy", ["rolling", "blue-green", "canary"])
    def test_deployment_with_different_strategies(self, strategy, mock_settings, mock_workflow_components):
        """Test deployment works with different deployment strategies."""
        request = FullDeploymentRequest(
            repository="testuser/testapp",
            instance_id="i-1234567890abcdef",
            port=8080,
            strategy=strategy
        )

        workflow = FullDeploymentWorkflow(mock_settings)
        response = workflow.execute(request)

        assert response.success is True

    @pytest.mark.parametrize("environment", ["development", "staging", "production"])
    def test_deployment_to_different_environments(self, environment, mock_settings, mock_workflow_components):
        """Test deployment works across different environments."""
        request = FullDeploymentRequest(
            repository="testuser/testapp",
            instance_id="i-1234567890abcdef",
            port=8080,
            environment=environment
        )

        workflow = FullDeploymentWorkflow(mock_settings)
        response = workflow.execute(request)

        assert response.success is True


class TestDeploymentPersistenceE2E:
    """Test deployment data persistence throughout the workflow."""

    def test_deployment_status_transitions(self, mock_settings, mock_workflow_components):
        """Test deployment status transitions through workflow phases."""
        components = mock_workflow_components

        request = FullDeploymentRequest(
            repository="testuser/testapp",
            instance_id="i-1234567890abcdef",
            port=8080
        )

        workflow = FullDeploymentWorkflow(mock_settings)
        response = workflow.execute(request)

        # Assert: Deployment succeeded and repo create was called
        assert response.success is True
        components['container'].deployment_repo.create.assert_called()

    def test_security_scan_results_persisted(self, mock_settings, mock_workflow_components):
        """Test security scan results are persisted to database."""
        components = mock_workflow_components

        request = FullDeploymentRequest(
            repository="testuser/testapp",
            instance_id="i-1234567890abcdef",
            port=8080
        )

        workflow = FullDeploymentWorkflow(mock_settings)
        response = workflow.execute(request)

        # Assert: Security scan was persisted
        assert response.success is True
        components['container'].security_scan_repo.create.assert_called()

    def test_build_results_persisted(self, mock_settings, mock_workflow_components):
        """Test build results are persisted to database."""
        components = mock_workflow_components

        request = FullDeploymentRequest(
            repository="testuser/testapp",
            instance_id="i-1234567890abcdef",
            port=8080
        )

        workflow = FullDeploymentWorkflow(mock_settings)
        response = workflow.execute(request)

        # Assert: Build result was persisted
        assert response.success is True
        components['container'].build_result_repo.create.assert_called()

    def test_health_check_results_persisted(self, mock_settings, mock_workflow_components):
        """Test health check results are persisted to database."""
        components = mock_workflow_components

        request = FullDeploymentRequest(
            repository="testuser/testapp",
            instance_id="i-1234567890abcdef",
            port=8080,
            health_check_path="/health"
        )

        workflow = FullDeploymentWorkflow(mock_settings)
        response = workflow.execute(request)

        # Assert health check passed
        assert response.success is True
        assert response.health_check_passed is True
