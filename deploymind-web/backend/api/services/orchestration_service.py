"""Orchestration service wrapping deploymind-core full deployment workflow."""
import sys
from pathlib import Path
from typing import Dict, Optional
import logging
import asyncio

# Add deploymind-core to path
core_path = Path(__file__).parent.parent.parent.parent.parent / "deploymind-core"
sys.path.insert(0, str(core_path))

try:
    from deploymind.application.use_cases.full_deployment_workflow import (
        FullDeploymentWorkflow,
        FullDeploymentRequest,
        FullDeploymentResponse
    )
    from deploymind.config.settings import Settings as CoreSettings
    CORE_AVAILABLE = True
except ImportError:
    FullDeploymentWorkflow = None
    FullDeploymentRequest = None
    FullDeploymentResponse = None
    CoreSettings = None
    CORE_AVAILABLE = False

logger = logging.getLogger(__name__)


class OrchestrationService:
    """
    Service for orchestrating full deployment workflows.

    Wraps deploymind-core's FullDeploymentWorkflow to execute:
    1. Security scanning (Trivy)
    2. Docker build
    3. EC2 deployment
    4. Health checks
    5. Auto-rollback on failure
    """

    def __init__(self):
        """Initialize orchestration service."""
        if CORE_AVAILABLE and CoreSettings and FullDeploymentWorkflow:
            try:
                settings = CoreSettings.load()
                self.workflow = FullDeploymentWorkflow(settings)
                logger.info("OrchestrationService initialized with core workflow")
            except Exception as e:
                logger.warning(f"Failed to initialize core workflow: {e}")
                self.workflow = None
        else:
            self.workflow = None
            logger.warning("Core deployment workflow not available, using mock mode")

    async def execute_full_deployment(
        self,
        repository: str,
        instance_id: str,
        port: int = 8080,
        strategy: str = "rolling",
        health_check_path: str = "/health",
        environment: str = "production",
        deployment_id: Optional[str] = None,
    ) -> Dict:
        """
        Execute complete deployment workflow.

        Pipeline:
        1. Validate inputs
        2. Clone GitHub repository
        3. Security scan (BLOCKING - fail stops deployment)
        4. Build Docker image
        5. Deploy to EC2 instance
        6. Run health checks
        7. Auto-rollback on failure

        Args:
            repository: GitHub repository in format "owner/repo"
            instance_id: AWS EC2 instance ID (e.g., "i-1234567890abcdef0")
            port: Application port (default: 8080)
            strategy: Deployment strategy (default: "rolling")
            health_check_path: Health check endpoint (default: "/health")
            environment: Environment name (default: "production")

        Returns:
            Dictionary with deployment results
        """
        if not self.workflow:
            return self._mock_deployment(repository, instance_id, deployment_id)

        try:
            # Create request
            request = FullDeploymentRequest(
                repository=repository,
                instance_id=instance_id,
                port=port,
                strategy=strategy,
                health_check_path=health_check_path,
                environment=environment,
                deployment_id=deployment_id,
            )

            # Execute workflow (this is synchronous, run in thread pool)
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                self.workflow.execute,
                request
            )

            # Convert response to dict
            return self._response_to_dict(response)

        except Exception as e:
            logger.error(f"Deployment workflow failed: {e}", exc_info=True)
            return {
                "success": False,
                "error_phase": "orchestration",
                "error_message": str(e),
                "deployment_id": None
            }

    async def rollback_deployment(
        self,
        instance_id: str,
        current_image_tag: str,
        previous_image_tag: str,
        port: int = 8080,
        health_check_path: str = "/health",
    ) -> Dict:
        """
        Roll back a deployment by re-deploying the previous image.

        Args:
            instance_id: AWS EC2 instance ID
            current_image_tag: Image tag currently running (for reference)
            previous_image_tag: Image tag to roll back to
            port: Application port
            health_check_path: Health check endpoint

        Returns:
            Dictionary with rollback result
        """
        if not CORE_AVAILABLE:
            return {"success": False, "error": "Core not available"}

        try:
            from deploymind.infrastructure.cloud.aws.ec2_client import EC2Client
            from deploymind.config.settings import Settings as CoreSettings

            settings = CoreSettings.load()
            ec2_client = EC2Client(settings)

            # Stop the currently running container
            logger.info(f"Rollback: stopping current container on {instance_id}")
            ec2_client.stop_container(instance_id, container_name="app")

            # Deploy the previous image
            logger.info(f"Rollback: deploying {previous_image_tag} on {instance_id}")
            deploy_result = ec2_client.deploy_container(
                instance_id=instance_id,
                image_tag=previous_image_tag,
                port=port,
                container_name="app",
                health_check_path=health_check_path,
            )

            return {
                "success": True,
                "previous_image_tag": previous_image_tag,
                "deploy_result": deploy_result,
            }

        except Exception as e:
            logger.error(f"Rollback failed: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    async def get_deployment_status(self, deployment_id: str) -> Dict:
        """
        Get current status of a deployment.

        Args:
            deployment_id: Deployment ID

        Returns:
            Dictionary with deployment status
        """
        # In production, this would query the database
        # For now, return a mock status
        return {
            "deployment_id": deployment_id,
            "status": "pending",
            "phase": "security_scanning"
        }

    def _response_to_dict(self, response: 'FullDeploymentResponse') -> Dict:
        """
        Convert FullDeploymentResponse to dictionary.

        Args:
            response: Response from core workflow

        Returns:
            Dictionary representation
        """
        return {
            "success": response.success,
            "deployment_id": response.deployment_id,
            "repository": response.repository,
            "commit_sha": response.commit_sha,

            # Security phase
            "security_passed": response.security_passed,
            "security_scan_id": response.security_scan_id,
            "vulnerabilities_found": response.vulnerabilities_found,

            # Build phase
            "build_successful": response.build_successful,
            "image_tag": response.image_tag,
            "image_size_mb": response.image_size_mb,

            # Deploy phase
            "deployment_successful": response.deployment_successful,
            "container_id": response.container_id,
            "health_check_passed": response.health_check_passed,
            "application_url": response.application_url,

            # Error handling
            "error_phase": response.error_phase,
            "error_message": response.error_message,
            "rollback_performed": response.rollback_performed,

            # Timing
            "duration_seconds": response.duration_seconds
        }

    def _mock_deployment(
        self,
        repository: str,
        instance_id: str,
        deployment_id: Optional[str] = None,
    ) -> Dict:
        """
        Mock deployment when core workflow not available.

        Args:
            repository: Repository name
            instance_id: Instance ID

        Returns:
            Mock deployment result
        """
        logger.info(f"Using mock deployment for {repository} on {instance_id}")

        return {
            "success": True,
            "deployment_id": deployment_id or "mock-deploy-123",
            "repository": repository,
            "commit_sha": "abc123def456",

            # Security phase
            "security_passed": True,
            "security_scan_id": "mock-scan-123",
            "vulnerabilities_found": 0,

            # Build phase
            "build_successful": True,
            "image_tag": f"{repository.replace('/', '-')}:latest",
            "image_size_mb": 150.0,

            # Deploy phase
            "deployment_successful": True,
            "container_id": "mock-container-123",
            "health_check_passed": True,
            "application_url": f"http://ec2-instance.amazonaws.com:8080",

            # Error handling
            "error_phase": None,
            "error_message": None,
            "rollback_performed": False,

            # Timing
            "duration_seconds": 45.0
        }
