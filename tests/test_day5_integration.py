"""Comprehensive tests for Day 5: Orchestrator & Integration.

Tests cover:
- Full deployment workflow (security → build → deploy)
- Redis pub/sub for real-time events
- Pipeline error handling at each stage
- Enhanced orchestrator functionality
- End-to-end integration
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

# Application layer
from application.use_cases.full_deployment_workflow import (
    FullDeploymentWorkflow,
    FullDeploymentRequest,
    FullDeploymentResponse
)

# Agents
from agents.enhanced_orchestrator import EnhancedOrchestrator, DeploymentProgress

# Infrastructure
from infrastructure.cache.redis_client import RedisClient

# Config and shared
from config.settings import Settings
from shared.exceptions import ValidationError


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
    settings.github_token = "test_github_token"
    settings.redis_url = "redis://localhost:6379"
    return settings


@pytest.fixture
def mock_redis_client():
    """Mock RedisClient."""
    client = Mock(spec=RedisClient)
    client.set_deployment_status = Mock()
    client.get_deployment_status = Mock(return_value="pending")
    client.publish_event = Mock()
    client.subscribe = Mock()
    return client


@pytest.fixture
def full_deployment_workflow(mock_settings):
    """Create FullDeploymentWorkflow with mocked dependencies."""
    workflow = FullDeploymentWorkflow(mock_settings)

    # Mock all use cases
    workflow.security_scan_use_case = Mock()
    workflow.build_use_case = Mock()
    workflow.deploy_use_case = Mock()
    workflow.github_client = Mock()
    workflow.redis_client = Mock()

    return workflow


@pytest.fixture
def enhanced_orchestrator(mock_settings):
    """Create EnhancedOrchestrator with mocked dependencies."""
    orchestrator = EnhancedOrchestrator(mock_settings)

    # Mock workflow
    orchestrator.workflow = Mock(spec=FullDeploymentWorkflow)
    orchestrator.redis_client = Mock(spec=RedisClient)

    return orchestrator


# =============================================================================
# TEST FULL DEPLOYMENT WORKFLOW
# =============================================================================

class TestFullDeploymentWorkflow:
    """Test complete deployment workflow orchestration."""

    def test_successful_full_deployment(self, full_deployment_workflow):
        """Test successful deployment through all phases."""
        workflow = full_deployment_workflow

        # Mock GitHub clone
        workflow.github_client.get_repository.return_value = {
            "default_branch": "main",
            "default_branch_commit_sha": "abc123def456"
        }
        workflow.github_client.clone_repository.return_value = None

        # Mock security scan - PASS
        security_response = Mock()
        security_response.success = True  # Changed from approved
        security_response.scan_result = Mock()
        security_response.scan_result.total_vulnerabilities = 2
        security_response.message = "Security scan passed"
        workflow.security_scan_use_case.execute.return_value = security_response

        # Mock build - SUCCESS
        build_response = Mock()
        build_response.success = True
        build_response.image_tag = "myapp:abc123"
        build_response.build_result = Mock()
        build_response.build_result.image_size_mb = 150.5
        build_response.message = "Build successful"
        workflow.build_use_case.execute.return_value = build_response

        # Mock deploy - SUCCESS
        deploy_response = Mock()
        deploy_response.success = True
        deploy_response.container_id = "container123"
        deploy_response.health_check_passed = True
        deploy_response.application_url = "http://1.2.3.4:8080"
        deploy_response.rollback_performed = False
        deploy_response.error_message = None
        workflow.deploy_use_case.execute.return_value = deploy_response

        # Execute workflow
        request = FullDeploymentRequest(
            repository="owner/repo",
            instance_id="i-1234567890abcdef0",
            port=8080
        )

        response = workflow.execute(request)

        # Assertions
        assert response.success is True
        assert response.security_passed is True
        assert response.build_successful is True
        assert response.deployment_successful is True
        assert response.image_tag == "myapp:abc123"
        assert response.application_url == "http://1.2.3.4:8080"
        assert response.error_phase is None
        assert response.rollback_performed is False

        # Verify all use cases were called
        workflow.security_scan_use_case.execute.assert_called_once()
        workflow.build_use_case.execute.assert_called_once()
        workflow.deploy_use_case.execute.assert_called_once()

    def test_security_scan_failure_blocks_pipeline(self, full_deployment_workflow):
        """Test that security scan failure stops the pipeline."""
        workflow = full_deployment_workflow

        # Mock GitHub clone
        workflow.github_client.get_repository.return_value = {
            "default_branch": "main",
            "default_branch_commit_sha": "abc123def456"
        }
        workflow.github_client.clone_repository.return_value = None

        # Mock security scan - FAIL
        security_response = Mock()
        security_response.success = False
        security_response.scan_result = Mock()
        security_response.scan_result.total_vulnerabilities = 10
        security_response.message = "5 CRITICAL vulnerabilities found"
        workflow.security_scan_use_case.execute.return_value = security_response

        # Execute workflow
        request = FullDeploymentRequest(
            repository="owner/repo",
            instance_id="i-1234567890abcdef0"
        )

        response = workflow.execute(request)

        # Assertions
        assert response.success is False
        assert response.security_passed is False
        assert response.error_phase == "security"
        assert "CRITICAL" in response.error_message

        # Build and deploy should NOT have been called
        workflow.build_use_case.execute.assert_not_called()
        workflow.deploy_use_case.execute.assert_not_called()

    def test_build_failure_stops_deployment(self, full_deployment_workflow):
        """Test that build failure prevents deployment."""
        workflow = full_deployment_workflow

        # Mock GitHub clone
        workflow.github_client.get_repository.return_value = {
            "default_branch": "main",
            "default_branch_commit_sha": "abc123def456"
        }
        workflow.github_client.clone_repository.return_value = None

        # Mock security scan - PASS
        security_response = Mock()
        security_response.success = True
        security_response.scan_result = Mock()
        security_response.scan_result.total_vulnerabilities = 0
        security_response.message = "Security scan passed"
        workflow.security_scan_use_case.execute.return_value = security_response

        # Mock build - FAIL
        build_response = Mock()
        build_response.success = False
        build_response.image_tag = None
        build_response.message = "Dockerfile syntax error at line 15"
        workflow.build_use_case.execute.return_value = build_response

        # Execute workflow
        request = FullDeploymentRequest(
            repository="owner/repo",
            instance_id="i-1234567890abcdef0"
        )

        response = workflow.execute(request)

        # Assertions
        assert response.success is False
        assert response.security_passed is True
        assert response.build_successful is False
        assert response.error_phase == "build"
        assert "Dockerfile syntax error" in response.error_message

        # Deploy should NOT have been called
        workflow.deploy_use_case.execute.assert_not_called()

    def test_deployment_failure_with_rollback(self, full_deployment_workflow):
        """Test deployment failure triggers rollback."""
        workflow = full_deployment_workflow

        # Mock GitHub clone
        workflow.github_client.get_repository.return_value = {
            "default_branch": "main",
            "default_branch_commit_sha": "abc123def456"
        }
        workflow.github_client.clone_repository.return_value = None

        # Mock security scan - PASS
        security_response = Mock()
        security_response.success = True
        security_response.scan_result = Mock()
        security_response.scan_result.total_vulnerabilities = 0
        security_response.message = "Security scan passed"
        workflow.security_scan_use_case.execute.return_value = security_response

        # Mock build - SUCCESS
        build_response = Mock()
        build_response.success = True
        build_response.image_tag = "myapp:abc123"
        build_response.build_result = Mock()
        build_response.build_result.image_size_mb = 150.5
        build_response.message = "Build successful"
        workflow.build_use_case.execute.return_value = build_response

        # Mock deploy - FAIL with rollback
        deploy_response = Mock()
        deploy_response.success = False
        deploy_response.container_id = None
        deploy_response.health_check_passed = False
        deploy_response.rollback_performed = True
        deploy_response.error_message = "Health checks failed - rolled back to previous version"
        workflow.deploy_use_case.execute.return_value = deploy_response

        # Execute workflow
        request = FullDeploymentRequest(
            repository="owner/repo",
            instance_id="i-1234567890abcdef0"
        )

        response = workflow.execute(request)

        # Assertions
        assert response.success is False
        assert response.security_passed is True
        assert response.build_successful is True
        assert response.deployment_successful is False
        assert response.error_phase == "deploy"
        assert response.rollback_performed is True
        assert "Health checks failed" in response.error_message

    def test_validation_error_handling(self, full_deployment_workflow):
        """Test that validation errors are handled properly."""
        workflow = full_deployment_workflow

        # Invalid instance ID
        request = FullDeploymentRequest(
            repository="owner/repo",
            instance_id="invalid-instance",  # Invalid format
            port=8080
        )

        response = workflow.execute(request)

        # Assertions
        assert response.success is False
        assert response.error_phase == "validation"
        assert "Invalid instance ID" in response.error_message

        # No use cases should have been called
        workflow.security_scan_use_case.execute.assert_not_called()
        workflow.build_use_case.execute.assert_not_called()
        workflow.deploy_use_case.execute.assert_not_called()


# =============================================================================
# TEST ENHANCED ORCHESTRATOR
# =============================================================================

class TestEnhancedOrchestrator:
    """Test enhanced orchestrator functionality."""

    def test_deploy_application_success(self, enhanced_orchestrator):
        """Test successful deployment through orchestrator."""
        orchestrator = enhanced_orchestrator

        # Mock workflow response
        workflow_response = FullDeploymentResponse(
            success=True,
            deployment_id="deploy-001",
            repository="owner/repo",
            commit_sha="abc123",
            security_passed=True,
            security_scan_id="scan-001",
            vulnerabilities_found=0,
            build_successful=True,
            image_tag="myapp:abc123",
            image_size_mb=150.0,
            deployment_successful=True,
            container_id="container123",
            health_check_passed=True,
            application_url="http://1.2.3.4:8080",
            duration_seconds=180.5
        )

        orchestrator.workflow.execute.return_value = workflow_response

        # Execute deployment
        response = orchestrator.deploy_application(
            repository="owner/repo",
            instance_id="i-1234567890abcdef0"
        )

        # Assertions
        assert response.success is True
        assert response.image_tag == "myapp:abc123"
        assert response.application_url == "http://1.2.3.4:8080"

        # Verify progress updates were made
        assert orchestrator.redis_client.set_deployment_status.called
        assert orchestrator.redis_client.publish_event.called

    def test_deploy_application_with_security_failure(self, enhanced_orchestrator):
        """Test deployment with security scan failure."""
        orchestrator = enhanced_orchestrator

        # Mock workflow response - security failed
        workflow_response = FullDeploymentResponse(
            success=False,
            deployment_id="deploy-002",
            repository="owner/repo",
            commit_sha="abc123",
            security_passed=False,
            vulnerabilities_found=5,
            error_phase="security",
            error_message="5 CRITICAL vulnerabilities found"
        )

        orchestrator.workflow.execute.return_value = workflow_response

        # Execute deployment
        response = orchestrator.deploy_application(
            repository="owner/repo",
            instance_id="i-1234567890abcdef0"
        )

        # Assertions
        assert response.success is False
        assert response.error_phase == "security"
        assert "CRITICAL" in response.error_message

    def test_get_deployment_status(self, enhanced_orchestrator):
        """Test getting deployment status from cache."""
        orchestrator = enhanced_orchestrator

        # Mock Redis responses
        orchestrator.redis_client.get_deployment_status.return_value = "completed"
        orchestrator.redis_client.get_deployment_data.side_effect = lambda dep_id, key: {
            "image_tag": "myapp:v1.0",
            "commit_sha": "abc123"
        }.get(key)

        # Get status
        status = orchestrator.get_deployment_status("deploy-001")

        # Assertions
        assert status is not None
        assert status["status"] == "completed"
        assert status["image_tag"] == "myapp:v1.0"
        assert status["commit_sha"] == "abc123"


# =============================================================================
# TEST REDIS PUB/SUB
# =============================================================================

class TestRedisPubSub:
    """Test Redis pub/sub functionality."""

    @patch('redis.from_url')
    def test_publish_event(self, mock_redis_from_url):
        """Test publishing events to Redis."""
        mock_redis = Mock()
        mock_redis_from_url.return_value = mock_redis

        redis_client = RedisClient("redis://localhost:6379")

        event = {
            "deployment_id": "deploy-001",
            "event_type": "security_scan_completed",
            "passed": True
        }

        redis_client.publish_event("deploymind:events", event)

        # Verify publish was called
        mock_redis.publish.assert_called_once()

    @patch('redis.from_url')
    def test_subscribe_to_events(self, mock_redis_from_url):
        """Test subscribing to events."""
        mock_redis = Mock()
        mock_pubsub = Mock()
        mock_redis.pubsub.return_value = mock_pubsub
        mock_redis_from_url.return_value = mock_redis

        redis_client = RedisClient("redis://localhost:6379")

        # Subscribe callback
        events_received = []

        def on_event(event):
            events_received.append(event)

        redis_client.subscribe("deploymind:events", on_event)

        # Verify subscription
        mock_pubsub.subscribe.assert_called_once_with("deploymind:events")

    @patch('redis.from_url')
    def test_deployment_status_caching(self, mock_redis_from_url):
        """Test deployment status caching."""
        mock_redis = Mock()
        mock_redis_from_url.return_value = mock_redis

        redis_client = RedisClient("redis://localhost:6379")

        # Set status
        redis_client.set_deployment_status("deploy-001", "in_progress")

        # Verify Redis set was called
        mock_redis.set.assert_called_once_with("deployment:deploy-001:status", "in_progress")
        mock_redis.expire.assert_called_once()

        # Get status
        mock_redis.get.return_value = b"in_progress"
        status = redis_client.get_deployment_status("deploy-001")

        assert status == "in_progress"


# =============================================================================
# TEST PIPELINE ERROR HANDLING
# =============================================================================

class TestPipelineErrorHandling:
    """Test error handling at each pipeline stage."""

    def test_github_clone_failure(self, full_deployment_workflow):
        """Test handling of GitHub clone failures."""
        workflow = full_deployment_workflow

        # Mock GitHub clone failure
        workflow.github_client.get_repository.side_effect = Exception("Repository not found")

        request = FullDeploymentRequest(
            repository="owner/nonexistent-repo",
            instance_id="i-1234567890abcdef0"
        )

        response = workflow.execute(request)

        # Should handle error gracefully
        assert response.success is False
        assert response.error_phase == "unknown"

    def test_security_scan_exception(self, full_deployment_workflow):
        """Test handling of security scan exceptions."""
        workflow = full_deployment_workflow

        # Mock GitHub clone success
        workflow.github_client.get_repository.return_value = {
            "default_branch": "main",
            "default_branch_commit_sha": "abc123"
        }

        # Mock security scan exception
        workflow.security_scan_use_case.execute.side_effect = Exception("Trivy scanner unavailable")

        request = FullDeploymentRequest(
            repository="owner/repo",
            instance_id="i-1234567890abcdef0"
        )

        response = workflow.execute(request)

        # Should return security failure
        assert response.success is False
        assert response.security_passed is False

    def test_invalid_health_check_path(self, full_deployment_workflow):
        """Test validation of health check path."""
        workflow = full_deployment_workflow

        # Health check path missing leading slash
        request = FullDeploymentRequest(
            repository="owner/repo",
            instance_id="i-1234567890abcdef0",
            health_check_path="health"  # Invalid - missing /
        )

        response = workflow.execute(request)

        # Should fail validation
        assert response.success is False
        assert response.error_phase == "validation"
        assert "Health check path must start with /" in response.error_message


# =============================================================================
# RUN TESTS
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
