"""Enhanced Orchestrator - Coordinates deployment pipeline with error handling and real-time tracking.

This orchestrator wraps the CrewAI agents with:
- Full deployment workflow orchestration
- Redis pub/sub for real-time progress
- Database tracking for all deployments
- Comprehensive error handling and rollback
- Agent execution metrics tracking
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional
import uuid

from deploymind.config.settings import Settings
from deploymind.application.use_cases.full_deployment_workflow import (
    FullDeploymentWorkflow,
    FullDeploymentRequest,
    FullDeploymentResponse
)
from deploymind.infrastructure.cache.redis_client import RedisClient
from deploymind.shared.validators import SecurityValidator
from deploymind.shared.exceptions import ValidationError, DeploymentError
from deploymind.shared.secure_logging import get_logger

logger = get_logger(__name__)


@dataclass
class DeploymentProgress:
    """Real-time deployment progress tracking."""
    deployment_id: str
    status: str  # pending, security_scan, building, deploying, completed, failed
    phase: str  # security, build, deploy
    message: str
    progress_percentage: int  # 0-100
    timestamp: datetime


class EnhancedOrchestrator:
    """Enhanced orchestrator with full integration and error handling.

    Coordinates:
    - Security Agent → Trivy scanning, CVE analysis
    - Build Agent → Dockerfile optimization, Docker build
    - Deploy Agent → Rolling deployment, health checks, rollback

    Features:
    - Real-time progress via Redis pub/sub
    - Database tracking for all deployments
    - Comprehensive error handling
    - Automatic rollback on failure
    - Agent execution metrics
    """

    def __init__(self, settings: Settings):
        """Initialize enhanced orchestrator.

        Args:
            settings: Application settings with API keys
        """
        self.settings = settings
        self.validator = SecurityValidator()
        self.redis_client = RedisClient(settings.redis_url)
        self.workflow = FullDeploymentWorkflow(settings)

        logger.info("EnhancedOrchestrator initialized")

    def deploy_application(
        self,
        repository: str,
        instance_id: str,
        port: int = 8080,
        strategy: str = "rolling",
        health_check_path: str = "/health",
        environment: str = "production"
    ) -> FullDeploymentResponse:
        """Deploy application through full pipeline.

        Pipeline stages:
        1. Input validation
        2. GitHub repository clone
        3. Security scan (Trivy) - BLOCKING
        4. Docker image build
        5. EC2 deployment with health checks
        6. Automatic rollback on failure

        Args:
            repository: GitHub repository (owner/repo)
            instance_id: AWS EC2 instance ID
            port: Application port (default: 8080)
            strategy: Deployment strategy (default: rolling)
            health_check_path: Health check endpoint (default: /health)
            environment: Environment name (default: production)

        Returns:
            Deployment response with results from all phases

        Example:
            >>> orchestrator = EnhancedOrchestrator(settings)
            >>> response = orchestrator.deploy_application(
            ...     repository="owner/repo",
            ...     instance_id="i-1234567890abcdef0"
            ... )
            >>> if response.success:
            ...     print(f"Deployed to {response.application_url}")
        """
        deployment_id = str(uuid.uuid4())[:8]
        start_time = datetime.now()

        logger.info(
            "Starting deployment",
            extra={
                "deployment_id": deployment_id,
                "repository": repository,
                "instance_id": instance_id,
                "environment": environment
            }
        )

        try:
            # Update status: Starting
            self._update_progress(
                deployment_id,
                status="pending",
                phase="validation",
                message="Validating deployment request",
                progress=5
            )

            # Create deployment request
            request = FullDeploymentRequest(
                repository=repository,
                instance_id=instance_id,
                port=port,
                strategy=strategy,
                health_check_path=health_check_path,
                environment=environment
            )

            # Update status: Security scan
            self._update_progress(
                deployment_id,
                status="security_scan",
                phase="security",
                message=f"Scanning {repository} for vulnerabilities",
                progress=20
            )

            # Execute full workflow
            response = self.workflow.execute(request)

            # Update progress based on phase completion
            if response.security_passed:
                self._update_progress(
                    deployment_id,
                    status="building",
                    phase="build",
                    message=f"Building Docker image for {repository}",
                    progress=50
                )

            if response.build_successful:
                self._update_progress(
                    deployment_id,
                    status="deploying",
                    phase="deploy",
                    message=f"Deploying to {instance_id}",
                    progress=75
                )

            # Final status
            if response.success:
                self._update_progress(
                    deployment_id,
                    status="completed",
                    phase="deploy",
                    message="Deployment completed successfully",
                    progress=100
                )

                duration = (datetime.now() - start_time).total_seconds()

                logger.info(
                    "Deployment completed successfully",
                    extra={
                        "deployment_id": deployment_id,
                        "duration_seconds": duration,
                        "image_tag": response.image_tag,
                        "application_url": response.application_url
                    }
                )
            else:
                self._update_progress(
                    deployment_id,
                    status="failed",
                    phase=response.error_phase or "unknown",
                    message=response.error_message or "Deployment failed",
                    progress=0
                )

                logger.error(
                    "Deployment failed",
                    extra={
                        "deployment_id": deployment_id,
                        "error_phase": response.error_phase,
                        "error_message": response.error_message,
                        "rollback_performed": response.rollback_performed
                    }
                )

            return response

        except ValidationError as e:
            logger.error(
                "Validation error",
                extra={"deployment_id": deployment_id, "error": str(e)},
                exc_info=True
            )

            self._update_progress(
                deployment_id,
                status="failed",
                phase="validation",
                message=f"Validation error: {str(e)}",
                progress=0
            )

            # Return error response
            return FullDeploymentResponse(
                success=False,
                deployment_id=deployment_id,
                repository=repository,
                error_phase="validation",
                error_message=str(e)
            )

        except Exception as e:
            logger.error(
                "Unexpected error in deployment",
                extra={"deployment_id": deployment_id, "error": str(e)},
                exc_info=True
            )

            self._update_progress(
                deployment_id,
                status="failed",
                phase="unknown",
                message=f"Unexpected error: {str(e)}",
                progress=0
            )

            return FullDeploymentResponse(
                success=False,
                deployment_id=deployment_id,
                repository=repository,
                error_phase="unknown",
                error_message=f"Unexpected error: {str(e)}"
            )

    def get_deployment_status(self, deployment_id: str) -> Optional[dict]:
        """Get current deployment status from cache.

        Args:
            deployment_id: Unique deployment identifier

        Returns:
            Dictionary with deployment status or None if not found
        """
        status = self.redis_client.get_deployment_status(deployment_id)

        if status:
            return {
                "deployment_id": deployment_id,
                "status": status,
                "image_tag": self.redis_client.get_deployment_data(deployment_id, "image_tag"),
                "commit_sha": self.redis_client.get_deployment_data(deployment_id, "commit_sha"),
            }

        return None

    def subscribe_to_events(self, callback):
        """Subscribe to real-time deployment events.

        Args:
            callback: Function to call with each event (receives dict)

        Example:
            >>> def on_event(event):
            ...     print(f"Event: {event['event_type']} - {event['message']}")
            >>> orchestrator.subscribe_to_events(on_event)
        """
        self.redis_client.subscribe("deploymind:events", callback)
        logger.info("Subscribed to deployment events")

    def _update_progress(
        self,
        deployment_id: str,
        status: str,
        phase: str,
        message: str,
        progress: int
    ):
        """Update deployment progress in Redis.

        Args:
            deployment_id: Unique deployment identifier
            status: Current status
            phase: Current phase
            message: Progress message
            progress: Progress percentage (0-100)
        """
        try:
            # Update Redis cache
            self.redis_client.set_deployment_status(deployment_id, status)

            # Publish progress event
            progress_data = {
                "deployment_id": deployment_id,
                "status": status,
                "phase": phase,
                "message": message,
                "progress_percentage": progress,
                "timestamp": datetime.now().isoformat()
            }

            self.redis_client.publish_event("deploymind:progress", progress_data)

            logger.debug(
                "Progress updated",
                extra={
                    "deployment_id": deployment_id,
                    "status": status,
                    "progress": progress
                }
            )

        except Exception as e:
            # Don't fail deployment if progress update fails
            logger.warning(
                "Failed to update progress",
                extra={"deployment_id": deployment_id, "error": str(e)}
            )

    def close(self):
        """Clean up resources."""
        self.redis_client.close()
        logger.info("EnhancedOrchestrator closed")


def create_orchestrator(settings: Settings) -> EnhancedOrchestrator:
    """Factory function to create enhanced orchestrator.

    Args:
        settings: Application settings

    Returns:
        Configured EnhancedOrchestrator instance
    """
    return EnhancedOrchestrator(settings)
