"""Deployment service to manage deployment lifecycle.

This service bridges deploymind-web and deploymind-core,
providing deployment creation and management capabilities.
"""
from typing import Optional
from sqlalchemy.orm import Session
import sys
from pathlib import Path

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
    ) -> bool:
        """
        Run the deployment workflow in background.

        This is a simplified version for Day 1.
        In Phase 2, this will call deploymind-core use cases.

        Args:
            deployment_id: Deployment ID

        Returns:
            True if successful
        """
        # Phase 2 TODO: Integrate with deploymind-core
        # For now, just simulate deployment steps with logs

        # Step 1: Security scanning
        self.add_log(
            deployment_id=deployment_id,
            level="INFO",
            message="Starting security scan...",
            agent="security",
        )

        # Step 2: Building
        self.update_deployment_status(
            deployment_id=deployment_id,
            status="building",
            message="Building Docker image...",
        )

        # Step 3: Deploying (simulated)
        self.update_deployment_status(
            deployment_id=deployment_id,
            status="deploying",
            message="Deploying to EC2 instance...",
        )

        # Step 4: Mark as deployed (simulated success)
        # In real scenario, this would wait for actual deployment
        self.update_deployment_status(
            deployment_id=deployment_id,
            status="deployed",
            message="Deployment completed successfully!",
        )

        return True
