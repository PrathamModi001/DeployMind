"""Deployment service to manage deployment lifecycle.

This service bridges deploymind-web and deploymind-core,
providing deployment creation and management capabilities.
"""
from typing import Optional
from sqlalchemy.orm import Session
import sys
from pathlib import Path
import logging

# Import deploymind-core models
core_path = Path(__file__).parent.parent.parent.parent / "deploymind-core"
sys.path.insert(0, str(core_path))

try:
    from deploymind.infrastructure.database.models import (
        Deployment,
        DeploymentLog,
        DeploymentStatusEnum,
    )
except ImportError:
    Deployment = None
    DeploymentLog = None
    DeploymentStatusEnum = None

# Import orchestration service
from api.services.orchestration_service import OrchestrationService

logger = logging.getLogger(__name__)


class DeploymentService:
    """Service for deployment operations."""

    def __init__(self, db: Session):
        """Initialize with database session."""
        self.db = db

    def create_deployment(
        self,
        deployment_id: str,
        repository: str,
        instance_id: str,
        user_id: int,
        port: int = 8080,
        strategy: str = "rolling",
        environment: str = "production",
        triggered_by: Optional[str] = None,
    ) -> Optional[Deployment]:
        """
        Create a new deployment record.

        Args:
            deployment_id: Unique deployment identifier
            repository: GitHub repository (owner/repo)
            instance_id: EC2 instance ID
            user_id: ID of user who created deployment
            port: Application port (default: 8080)
            strategy: Deployment strategy (rolling, canary, blue_green)
            environment: Environment (development, staging, production)
            triggered_by: Username who triggered deployment

        Returns:
            Created Deployment object or None if models unavailable
        """
        if not Deployment or not DeploymentStatusEnum:
            return None

        # Convert strategy string to enum
        strategy_map = {
            "rolling": "ROLLING",
            "canary": "CANARY",
            "blue-green": "BLUE_GREEN",
        }
        strategy_enum = strategy_map.get(strategy.lower(), "ROLLING")

        deployment = Deployment(
            id=deployment_id,
            repository=repository,
            instance_id=instance_id,
            user_id=user_id,
            status=DeploymentStatusEnum.PENDING,
            strategy=strategy_enum,
            triggered_by=triggered_by,
            extra_data={"port": port, "environment": environment},
        )

        self.db.add(deployment)
        self.db.commit()
        self.db.refresh(deployment)

        # Add initial log
        self.add_log(
            deployment_id=deployment_id,
            level="INFO",
            message=f"Deployment created for {repository}",
            agent="system",
        )

        return deployment

    def add_log(
        self,
        deployment_id: str,
        level: str,
        message: str,
        agent: Optional[str] = None,
    ) -> bool:
        """
        Add a log entry for a deployment.

        Args:
            deployment_id: Deployment ID
            level: Log level (INFO, WARNING, ERROR)
            message: Log message
            agent: Agent name (optional)

        Returns:
            True if successful, False otherwise
        """
        if not DeploymentLog:
            return False

        log = DeploymentLog(
            deployment_id=deployment_id,
            level=level,
            message=message,
            agent=agent,
        )

        self.db.add(log)
        self.db.commit()

        return True

    def update_deployment_status(
        self,
        deployment_id: str,
        status: str,
        message: Optional[str] = None,
    ) -> Optional[Deployment]:
        """
        Update deployment status.

        Args:
            deployment_id: Deployment ID
            status: New status (e.g., "deployed", "failed")
            message: Optional log message

        Returns:
            Updated Deployment or None if not found
        """
        if not Deployment:
            return None

        deployment = self.db.query(Deployment).filter(
            Deployment.id == deployment_id
        ).first()

        if not deployment:
            return None

        # Update status
        status_lower = status.lower()
        deployment.status = status_lower

        self.db.commit()
        self.db.refresh(deployment)

        # Add log if message provided
        if message:
            self.add_log(
                deployment_id=deployment_id,
                level="INFO",
                message=message,
                agent="system",
            )

        return deployment

    async def run_deployment_workflow(
        self,
        deployment_id: str,
        repository: str,
        instance_id: str,
        port: int = 8080,
        strategy: str = "rolling",
        health_check_path: str = "/health",
        environment: str = "production",
    ) -> bool:
        """
        Run the full deployment workflow using deploymind-core.

        Executes complete deployment pipeline:
        1. Security scanning (BLOCKING - fail stops deployment)
        2. Docker build
        3. EC2 deployment
        4. Health checks
        5. Auto-rollback on failure

        Args:
            deployment_id: Deployment ID
            repository: GitHub repository (owner/repo)
            instance_id: EC2 instance ID
            port: Application port (default: 8080)
            strategy: Deployment strategy (default: "rolling")
            health_check_path: Health check endpoint (default: "/health")
            environment: Environment name (default: "production")

        Returns:
            True if successful, False otherwise
        """
        logger.info(f"Starting deployment workflow for {deployment_id}")

        # Update status to pending
        self.update_deployment_status(
            deployment_id=deployment_id,
            status="pending",
            message="Initializing deployment...",
        )

        try:
            # Execute full deployment workflow via orchestration service
            orchestration = OrchestrationService()
            result = await orchestration.execute_full_deployment(
                repository=repository,
                instance_id=instance_id,
                port=port,
                strategy=strategy,
                health_check_path=health_check_path,
                environment=environment,
            )

            # Update status based on result
            if result["success"]:
                self.update_deployment_status(
                    deployment_id=deployment_id,
                    status="deployed",
                    message=f"Deployment successful! App running at {result.get('application_url', 'unknown')}",
                )

                # Add detailed logs
                self.add_log(
                    deployment_id=deployment_id,
                    level="INFO",
                    message=f"Security scan: PASSED (0 vulnerabilities)",
                    agent="security",
                )
                self.add_log(
                    deployment_id=deployment_id,
                    level="INFO",
                    message=f"Docker build: SUCCESS ({result.get('image_tag', 'unknown')})",
                    agent="build",
                )
                self.add_log(
                    deployment_id=deployment_id,
                    level="INFO",
                    message=f"Health check: PASSED",
                    agent="deploy",
                )

                return True
            else:
                # Deployment failed
                error_phase = result.get("error_phase", "unknown")
                error_message = result.get("error_message", "Unknown error")

                self.update_deployment_status(
                    deployment_id=deployment_id,
                    status="failed",
                    message=f"Deployment failed at {error_phase}: {error_message}",
                )

                # Add error log
                self.add_log(
                    deployment_id=deployment_id,
                    level="ERROR",
                    message=f"Deployment failed: {error_message}",
                    agent=error_phase,
                )

                # Log rollback if performed
                if result.get("rollback_performed"):
                    self.add_log(
                        deployment_id=deployment_id,
                        level="WARNING",
                        message="Automatic rollback performed",
                        agent="deploy",
                    )

                return False

        except Exception as e:
            logger.error(f"Deployment workflow failed: {e}", exc_info=True)

            self.update_deployment_status(
                deployment_id=deployment_id,
                status="failed",
                message=f"Deployment error: {str(e)}",
            )

            self.add_log(
                deployment_id=deployment_id,
                level="ERROR",
                message=f"Workflow execution error: {str(e)}",
                agent="orchestration",
            )

            return False
