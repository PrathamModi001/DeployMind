"""Tests for orchestration service wrapping deploymind-core workflows."""
import pytest
from unittest.mock import Mock, patch, MagicMock
from io import BytesIO

from api.services.orchestration_service import OrchestrationService


@pytest.fixture
def mock_workflow_response():
    """Mock FullDeploymentResponse from core."""
    response = Mock()
    response.success = True
    response.deployment_id = "deploy-123"
    response.repository = "owner/repo"
    response.commit_sha = "abc123def456"
    response.security_passed = True
    response.security_scan_id = "scan-123"
    response.vulnerabilities_found = 0
    response.build_successful = True
    response.image_tag = "owner-repo:abc123"
    response.image_size_mb = 150.0
    response.deployment_successful = True
    response.container_id = "container-123"
    response.health_check_passed = True
    response.application_url = "http://ec2-instance.amazonaws.com:8080"
    response.error_phase = None
    response.error_message = None
    response.rollback_performed = False
    response.duration_seconds = 45.0
    return response


@pytest.fixture
def mock_workflow_failure():
    """Mock failed deployment response."""
    response = Mock()
    response.success = False
    response.deployment_id = "deploy-456"
    response.repository = "owner/repo"
    response.commit_sha = "abc123def456"
    response.security_passed = False
    response.security_scan_id = "scan-456"
    response.vulnerabilities_found = 5
    response.build_successful = False
    response.image_tag = None
    response.image_size_mb = 0.0
    response.deployment_successful = False
    response.container_id = None
    response.health_check_passed = False
    response.application_url = None
    response.error_phase = "security_scan"
    response.error_message = "CRITICAL vulnerabilities found"
    response.rollback_performed = False
    response.duration_seconds = 10.0
    return response


class TestOrchestrationService:
    """Test orchestration service basic functionality."""

    @patch('api.services.orchestration_service.CORE_AVAILABLE', True)
    @patch('api.services.orchestration_service.FullDeploymentRequest')
    @patch('api.services.orchestration_service.FullDeploymentWorkflow')
    @patch('api.services.orchestration_service.CoreSettings')
    @pytest.mark.asyncio
    async def test_successful_deployment(self, mock_settings, mock_workflow_class, mock_request_class, mock_workflow_response):
        """Test successful full deployment workflow."""
        # Setup mocks
        mock_settings.load.return_value = Mock()
        mock_workflow = Mock()
        mock_workflow.execute.return_value = mock_workflow_response
        mock_workflow_class.return_value = mock_workflow

        # Mock request creation
        mock_request = Mock()
        mock_request_class.return_value = mock_request

        # Execute
        service = OrchestrationService()
        result = await service.execute_full_deployment(
            repository="owner/repo",
            instance_id="i-1234567890abcdef0",
            port=8080,
            strategy="rolling",
            health_check_path="/health",
            environment="production"
        )

        # Verify
        assert result["success"] is True
        assert result["deployment_id"] == "deploy-123"
        assert result["repository"] == "owner/repo"
        assert result["security_passed"] is True
        assert result["build_successful"] is True
        assert result["deployment_successful"] is True
        assert result["health_check_passed"] is True
        assert result["error_phase"] is None
        assert result["rollback_performed"] is False

    @patch('api.services.orchestration_service.CORE_AVAILABLE', True)
    @patch('api.services.orchestration_service.FullDeploymentRequest')
    @patch('api.services.orchestration_service.FullDeploymentWorkflow')
    @patch('api.services.orchestration_service.CoreSettings')
    @pytest.mark.asyncio
    async def test_security_scan_failure(self, mock_settings, mock_workflow_class, mock_request_class, mock_workflow_failure):
        """Test deployment stops on security scan failure."""
        # Setup mocks
        mock_settings.load.return_value = Mock()
        mock_workflow = Mock()
        mock_workflow.execute.return_value = mock_workflow_failure
        mock_workflow_class.return_value = mock_workflow
        mock_request_class.return_value = Mock()

        # Execute
        service = OrchestrationService()
        result = await service.execute_full_deployment(
            repository="owner/repo",
            instance_id="i-1234567890abcdef0"
        )

        # Verify pipeline stopped at security phase
        assert result["success"] is False
        assert result["error_phase"] == "security_scan"
        assert result["security_passed"] is False
        assert result["vulnerabilities_found"] == 5
        assert result["build_successful"] is False
        assert result["deployment_successful"] is False

    @patch('api.services.orchestration_service.CORE_AVAILABLE', True)
    @patch('api.services.orchestration_service.FullDeploymentRequest')
    @patch('api.services.orchestration_service.FullDeploymentWorkflow')
    @patch('api.services.orchestration_service.CoreSettings')
    @pytest.mark.asyncio
    async def test_build_failure(self, mock_settings, mock_workflow_class, mock_request_class):
        """Test deployment stops on build failure."""
        # Setup response with build failure
        response = Mock()
        response.success = False
        response.deployment_id = "deploy-789"
        response.repository = "owner/repo"
        response.commit_sha = "xyz789"
        response.security_passed = True  # Security passed
        response.security_scan_id = "scan-789"
        response.vulnerabilities_found = 0
        response.build_successful = False  # Build failed
        response.image_tag = None
        response.image_size_mb = 0.0
        response.deployment_successful = False
        response.container_id = None
        response.health_check_passed = False
        response.application_url = None
        response.error_phase = "build"
        response.error_message = "Docker build failed: syntax error in Dockerfile"
        response.rollback_performed = False
        response.duration_seconds = 20.0

        mock_settings.load.return_value = Mock()
        mock_workflow = Mock()
        mock_workflow.execute.return_value = response
        mock_workflow_class.return_value = mock_workflow
        mock_request_class.return_value = Mock()

        # Execute
        service = OrchestrationService()
        result = await service.execute_full_deployment(
            repository="owner/repo",
            instance_id="i-1234567890abcdef0"
        )

        # Verify
        assert result["success"] is False
        assert result["error_phase"] == "build"
        assert result["security_passed"] is True
        assert result["build_successful"] is False
        assert result["deployment_successful"] is False

    @patch('api.services.orchestration_service.CORE_AVAILABLE', True)
    @patch('api.services.orchestration_service.FullDeploymentRequest')
    @patch('api.services.orchestration_service.FullDeploymentWorkflow')
    @patch('api.services.orchestration_service.CoreSettings')
    @pytest.mark.asyncio
    async def test_deployment_failure_with_rollback(self, mock_settings, mock_workflow_class, mock_request_class):
        """Test deployment failure triggers automatic rollback."""
        # Setup response with deployment failure and rollback
        response = Mock()
        response.success = False
        response.deployment_id = "deploy-rollback"
        response.repository = "owner/repo"
        response.commit_sha = "rollback123"
        response.security_passed = True
        response.security_scan_id = "scan-rollback"
        response.vulnerabilities_found = 0
        response.build_successful = True
        response.image_tag = "owner-repo:rollback123"
        response.image_size_mb = 150.0
        response.deployment_successful = False
        response.container_id = None
        response.health_check_passed = False
        response.application_url = None
        response.error_phase = "health_check"
        response.error_message = "Health check failed after 5 attempts"
        response.rollback_performed = True  # Rollback happened
        response.duration_seconds = 120.0

        mock_settings.load.return_value = Mock()
        mock_workflow = Mock()
        mock_workflow.execute.return_value = response
        mock_workflow_class.return_value = mock_workflow
        mock_request_class.return_value = Mock()

        # Execute
        service = OrchestrationService()
        result = await service.execute_full_deployment(
            repository="owner/repo",
            instance_id="i-1234567890abcdef0"
        )

        # Verify
        assert result["success"] is False
        assert result["error_phase"] == "health_check"
        assert result["rollback_performed"] is True
        assert result["security_passed"] is True
        assert result["build_successful"] is True
        assert result["deployment_successful"] is False
        assert result["health_check_passed"] is False

    @pytest.mark.asyncio
    async def test_core_unavailable_mock_mode(self):
        """Test service falls back to mock mode when core unavailable."""
        # Service initializes without core
        with patch('api.services.orchestration_service.CORE_AVAILABLE', False):
            service = OrchestrationService()
            result = await service.execute_full_deployment(
                repository="owner/repo",
                instance_id="i-1234567890abcdef0"
            )

        # Verify mock response
        assert result["success"] is True
        assert result["deployment_id"] == "mock-deploy-123"
        assert result["repository"] == "owner/repo"
        assert result["commit_sha"] == "abc123def456"
        assert result["security_passed"] is True
        assert result["build_successful"] is True
        assert result["deployment_successful"] is True

    @patch('api.services.orchestration_service.CORE_AVAILABLE', True)
    @patch('api.services.orchestration_service.FullDeploymentRequest')
    @patch('api.services.orchestration_service.FullDeploymentWorkflow')
    @patch('api.services.orchestration_service.CoreSettings')
    @pytest.mark.asyncio
    async def test_workflow_exception_handling(self, mock_settings, mock_workflow_class, mock_request_class):
        """Test exception handling during workflow execution."""
        # Setup workflow to raise exception
        mock_settings.load.return_value = Mock()
        mock_workflow = Mock()
        mock_workflow.execute.side_effect = Exception("Unexpected workflow error")
        mock_workflow_class.return_value = mock_workflow
        mock_request_class.return_value = Mock()

        # Execute
        service = OrchestrationService()
        result = await service.execute_full_deployment(
            repository="owner/repo",
            instance_id="i-1234567890abcdef0"
        )

        # Verify error response
        assert result["success"] is False
        assert result["error_phase"] == "orchestration"
        assert "Unexpected workflow error" in result["error_message"]
        assert result["deployment_id"] is None

    @patch('api.services.orchestration_service.CORE_AVAILABLE', True)
    @patch('api.services.orchestration_service.FullDeploymentRequest')
    @patch('api.services.orchestration_service.FullDeploymentWorkflow')
    @patch('api.services.orchestration_service.CoreSettings')
    @pytest.mark.asyncio
    async def test_custom_deployment_parameters(self, mock_settings, mock_workflow_class, mock_request_class, mock_workflow_response):
        """Test deployment with custom parameters."""
        mock_settings.load.return_value = Mock()
        mock_workflow = Mock()
        mock_workflow.execute.return_value = mock_workflow_response
        mock_workflow_class.return_value = mock_workflow

        # Mock request to track parameters
        mock_request = Mock()
        mock_request_class.return_value = mock_request

        # Execute with custom params
        service = OrchestrationService()
        result = await service.execute_full_deployment(
            repository="owner/custom-repo",
            instance_id="i-custom123",
            port=3000,
            strategy="blue_green",
            health_check_path="/api/health",
            environment="staging"
        )

        # Verify success
        assert result["success"] is True
        assert result["deployment_id"] == "deploy-123"

        # Verify request was called with correct parameters (deployment_id may be None or passed)
        call_kwargs = mock_request_class.call_args
        assert call_kwargs is not None
        kwargs = call_kwargs.kwargs if call_kwargs.kwargs else {}
        args = call_kwargs.args if call_kwargs.args else ()
        # Verify all expected params were passed (positional or keyword)
        call_str = str(call_kwargs)
        assert "owner/custom-repo" in call_str
        assert "i-custom123" in call_str
        assert "3000" in call_str

    @pytest.mark.asyncio
    async def test_get_deployment_status(self):
        """Test deployment status retrieval."""
        service = OrchestrationService()
        status = await service.get_deployment_status("deploy-123")

        # Verify status structure (mock for now)
        assert "deployment_id" in status
        assert "status" in status
        assert "phase" in status
        assert status["deployment_id"] == "deploy-123"


class TestOrchestrationEdgeCases:
    """Test edge cases for orchestration service."""

    @pytest.mark.asyncio
    async def test_very_long_repository_name(self):
        """Test with very long repository name."""
        service = OrchestrationService()
        long_name = "owner/" + "a" * 200
        result = await service.execute_full_deployment(
            repository=long_name,
            instance_id="i-1234567890abcdef0"
        )

        # Should handle gracefully (mock mode)
        assert "deployment_id" in result

    @pytest.mark.asyncio
    async def test_special_characters_in_repository(self):
        """Test repository name with special characters."""
        service = OrchestrationService()
        result = await service.execute_full_deployment(
            repository="owner/repo-name.with-special_chars",
            instance_id="i-1234567890abcdef0"
        )

        # Should handle gracefully
        assert "deployment_id" in result

    @pytest.mark.asyncio
    async def test_invalid_instance_id_format(self):
        """Test with invalid EC2 instance ID format."""
        service = OrchestrationService()
        result = await service.execute_full_deployment(
            repository="owner/repo",
            instance_id="invalid-instance-id"
        )

        # Should still return response (validation happens in core)
        assert "deployment_id" in result

    @pytest.mark.asyncio
    async def test_zero_port_number(self):
        """Test with port number 0."""
        service = OrchestrationService()
        result = await service.execute_full_deployment(
            repository="owner/repo",
            instance_id="i-1234567890abcdef0",
            port=0
        )

        # Should handle gracefully
        assert "deployment_id" in result

    @pytest.mark.asyncio
    async def test_negative_port_number(self):
        """Test with negative port number."""
        service = OrchestrationService()
        result = await service.execute_full_deployment(
            repository="owner/repo",
            instance_id="i-1234567890abcdef0",
            port=-1
        )

        # Should handle gracefully
        assert "deployment_id" in result

    @pytest.mark.asyncio
    async def test_very_high_port_number(self):
        """Test with port number above valid range."""
        service = OrchestrationService()
        result = await service.execute_full_deployment(
            repository="owner/repo",
            instance_id="i-1234567890abcdef0",
            port=99999
        )

        # Should handle gracefully
        assert "deployment_id" in result

    @pytest.mark.asyncio
    async def test_empty_repository_name(self):
        """Test with empty repository name."""
        service = OrchestrationService()
        result = await service.execute_full_deployment(
            repository="",
            instance_id="i-1234567890abcdef0"
        )

        # Should handle gracefully
        assert "deployment_id" in result

    @pytest.mark.asyncio
    async def test_empty_instance_id(self):
        """Test with empty instance ID."""
        service = OrchestrationService()
        result = await service.execute_full_deployment(
            repository="owner/repo",
            instance_id=""
        )

        # Should handle gracefully
        assert "deployment_id" in result

    @pytest.mark.asyncio
    async def test_invalid_deployment_strategy(self):
        """Test with invalid deployment strategy."""
        service = OrchestrationService()
        result = await service.execute_full_deployment(
            repository="owner/repo",
            instance_id="i-1234567890abcdef0",
            strategy="invalid_strategy"
        )

        # Should handle gracefully
        assert "deployment_id" in result

    @pytest.mark.asyncio
    async def test_empty_health_check_path(self):
        """Test with empty health check path."""
        service = OrchestrationService()
        result = await service.execute_full_deployment(
            repository="owner/repo",
            instance_id="i-1234567890abcdef0",
            health_check_path=""
        )

        # Should handle gracefully
        assert "deployment_id" in result

    @pytest.mark.asyncio
    async def test_health_check_path_with_query_params(self):
        """Test health check path with query parameters."""
        service = OrchestrationService()
        result = await service.execute_full_deployment(
            repository="owner/repo",
            instance_id="i-1234567890abcdef0",
            health_check_path="/health?check=full&timeout=30"
        )

        # Should handle gracefully
        assert "deployment_id" in result

    @patch('api.services.orchestration_service.CoreSettings')
    @pytest.mark.asyncio
    async def test_settings_initialization_failure(self, mock_settings):
        """Test when CoreSettings fails to initialize."""
        mock_settings.load.side_effect = Exception("Settings error")

        # Service should handle initialization failure
        service = OrchestrationService()
        result = await service.execute_full_deployment(
            repository="owner/repo",
            instance_id="i-1234567890abcdef0"
        )

        # Should fall back to mock mode
        assert result["deployment_id"] == "mock-deploy-123"

    @patch('api.services.orchestration_service.CORE_AVAILABLE', True)
    @patch('api.services.orchestration_service.FullDeploymentRequest')
    @patch('api.services.orchestration_service.FullDeploymentWorkflow')
    @patch('api.services.orchestration_service.CoreSettings')
    @pytest.mark.asyncio
    async def test_concurrent_deployments(self, mock_settings, mock_workflow_class, mock_request_class, mock_workflow_response):
        """Test multiple concurrent deployments."""
        import asyncio

        mock_settings.load.return_value = Mock()
        mock_workflow = Mock()
        mock_workflow.execute.return_value = mock_workflow_response
        mock_workflow_class.return_value = mock_workflow
        mock_request_class.return_value = Mock()

        service = OrchestrationService()

        # Execute 5 concurrent deployments
        tasks = [
            service.execute_full_deployment(
                repository=f"owner/repo{i}",
                instance_id=f"i-instance{i}"
            )
            for i in range(5)
        ]

        results = await asyncio.gather(*tasks)

        # All should succeed
        assert len(results) == 5
        for result in results:
            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_unicode_in_repository_name(self):
        """Test repository name with unicode characters."""
        service = OrchestrationService()
        result = await service.execute_full_deployment(
            repository="owner/репо-名前-🚀",
            instance_id="i-1234567890abcdef0"
        )

        # Should handle gracefully
        assert "deployment_id" in result

    @pytest.mark.asyncio
    async def test_sql_injection_attempt_in_repository(self):
        """Test SQL injection attempt in repository name."""
        service = OrchestrationService()
        result = await service.execute_full_deployment(
            repository="owner/repo'; DROP TABLE deployments;--",
            instance_id="i-1234567890abcdef0"
        )

        # Should handle gracefully without executing SQL
        assert "deployment_id" in result

    @pytest.mark.asyncio
    async def test_path_traversal_attempt_in_repository(self):
        """Test path traversal attempt in repository name."""
        service = OrchestrationService()
        result = await service.execute_full_deployment(
            repository="../../etc/passwd",
            instance_id="i-1234567890abcdef0"
        )

        # Should handle gracefully
        assert "deployment_id" in result

    @pytest.mark.asyncio
    async def test_xss_attempt_in_environment(self):
        """Test XSS attempt in environment parameter."""
        service = OrchestrationService()
        result = await service.execute_full_deployment(
            repository="owner/repo",
            instance_id="i-1234567890abcdef0",
            environment="<script>alert('xss')</script>"
        )

        # Should handle gracefully
        assert "deployment_id" in result

    @patch('api.services.orchestration_service.CORE_AVAILABLE', True)
    @patch('api.services.orchestration_service.FullDeploymentRequest')
    @patch('api.services.orchestration_service.FullDeploymentWorkflow')
    @patch('api.services.orchestration_service.CoreSettings')
    @pytest.mark.asyncio
    async def test_response_with_missing_fields(self, mock_settings, mock_workflow_class, mock_request_class):
        """Test handling response with missing optional fields."""
        # Create response with minimal fields
        response = Mock()
        response.success = True
        response.deployment_id = "minimal-123"
        response.repository = "owner/repo"
        response.commit_sha = None  # Missing
        response.security_passed = True
        response.security_scan_id = None  # Missing
        response.vulnerabilities_found = 0
        response.build_successful = True
        response.image_tag = None  # Missing
        response.image_size_mb = None  # Missing
        response.deployment_successful = True
        response.container_id = None  # Missing
        response.health_check_passed = True
        response.application_url = None  # Missing
        response.error_phase = None
        response.error_message = None
        response.rollback_performed = False
        response.duration_seconds = None  # Missing

        mock_settings.load.return_value = Mock()
        mock_workflow = Mock()
        mock_workflow.execute.return_value = response
        mock_workflow_class.return_value = mock_workflow
        mock_request_class.return_value = Mock()

        service = OrchestrationService()
        result = await service.execute_full_deployment(
            repository="owner/repo",
            instance_id="i-1234567890abcdef0"
        )

        # Should handle None values gracefully
        assert result["success"] is True
        assert result["deployment_id"] == "minimal-123"
        assert result["commit_sha"] is None
        assert result["image_tag"] is None

    @pytest.mark.asyncio
    async def test_deployment_status_with_special_characters(self):
        """Test deployment status with special character deployment ID."""
        service = OrchestrationService()
        status = await service.get_deployment_status("deploy-<script>")

        # Should handle gracefully
        assert "deployment_id" in status
        assert status["deployment_id"] == "deploy-<script>"
