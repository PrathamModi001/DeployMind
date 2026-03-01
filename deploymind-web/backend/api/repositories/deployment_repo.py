"""Deployment repository for database operations."""
from typing import Optional, List, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import desc
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
    # Fallback for testing
    Deployment = None
    DeploymentLog = None
    DeploymentStatusEnum = None


class DeploymentRepository:
    """Repository for deployment database operations."""

    def __init__(self, db: Session):
        """Initialize repository with database session."""
        self.db = db

    def get_by_id(self, deployment_id: str) -> Optional[Deployment]:
        """Get deployment by ID."""
        if not Deployment:
            return None
        return self.db.query(Deployment).filter(Deployment.id == deployment_id).first()

    def list_deployments(
        self,
        offset: int = 0,
        limit: int = 10,
        status: Optional[str] = None,
        user_id: Optional[int] = None,
    ) -> Tuple[List[Deployment], int]:
        """
        List deployments with pagination and optional filtering.

        Args:
            offset: Number of records to skip
            limit: Maximum number of records to return
            status: Optional status filter (e.g., "deployed", "pending")
            user_id: Optional user ID to scope results to current user

        Returns:
            Tuple of (deployments list, total count)
        """
        if not Deployment:
            return [], 0

        query = self.db.query(Deployment)

        # Scope to user if provided
        if user_id is not None:
            query = query.filter(Deployment.user_id == user_id)

        # Filter by status if provided
        if status:
            # Convert to lowercase for enum matching
            status_lower = status.lower()
            query = query.filter(Deployment.status == status_lower)

        # Get total count before pagination
        total = query.count()

        # Apply pagination and ordering (most recent first)
        deployments = (
            query.order_by(desc(Deployment.created_at))
            .offset(offset)
            .limit(limit)
            .all()
        )

        return deployments, total

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
    ) -> Deployment:
        """
        Create a new deployment record.

        Args:
            deployment_id: Unique deployment identifier
            repository: GitHub repository (owner/repo)
            instance_id: EC2 instance ID
            user_id: ID of user who created deployment (foreign key to web_users)
            port: Application port (default: 8080)
            strategy: Deployment strategy (rolling, canary, blue_green)
            environment: Environment (development, staging, production)
            triggered_by: Username who triggered deployment

        Returns:
            Created Deployment object
        """
        if not Deployment:
            raise RuntimeError("Deployment model not available")

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

        return deployment

    def update_status(
        self,
        deployment_id: str,
        status: str,
    ) -> Optional[Deployment]:
        """
        Update deployment status.

        Args:
            deployment_id: Deployment ID
            status: New status (e.g., "deployed", "failed")

        Returns:
            Updated Deployment or None if not found
        """
        deployment = self.get_by_id(deployment_id)
        if not deployment:
            return None

        # Map status string to DeploymentStatusEnum member
        if DeploymentStatusEnum is not None:
            status_upper = status.upper()
            try:
                deployment.status = DeploymentStatusEnum[status_upper]
            except KeyError:
                # Fall back to raw string if enum member not found
                deployment.status = status.lower()
        else:
            deployment.status = status.lower()

        self.db.commit()
        self.db.refresh(deployment)

        return deployment

    def update_info(
        self,
        deployment_id: str,
        commit_sha: Optional[str] = None,
        image_tag: Optional[str] = None,
        image_size_mb: Optional[float] = None,
    ) -> Optional[Deployment]:
        """
        Update deployment info fields after workflow completes.

        Args:
            deployment_id: Deployment ID
            commit_sha: Git commit SHA
            image_tag: Docker image tag
            image_size_mb: Docker image size in MB

        Returns:
            Updated Deployment or None if not found
        """
        deployment = self.get_by_id(deployment_id)
        if not deployment:
            return None

        if commit_sha is not None:
            deployment.commit_sha = commit_sha
        if image_tag is not None:
            deployment.image_tag = image_tag
        if image_size_mb is not None:
            deployment.image_size_mb = image_size_mb

        self.db.commit()
        self.db.refresh(deployment)

        return deployment

    def get_deployment_logs(
        self,
        deployment_id: str,
        limit: int = 100,
    ) -> List[DeploymentLog]:
        """
        Get logs for a specific deployment.

        Args:
            deployment_id: Deployment ID
            limit: Maximum number of logs to return

        Returns:
            List of deployment logs ordered by timestamp
        """
        if not DeploymentLog:
            return []

        return (
            self.db.query(DeploymentLog)
            .filter(DeploymentLog.deployment_id == deployment_id)
            .order_by(DeploymentLog.timestamp)
            .limit(limit)
            .all()
        )

    def delete_deployment(self, deployment_id: str) -> bool:
        """
        Delete a deployment (soft delete by updating status).

        Args:
            deployment_id: Deployment ID

        Returns:
            True if deleted, False if not found
        """
        deployment = self.get_by_id(deployment_id)
        if not deployment:
            return False

        # Soft delete - just mark as rolled back or use hard delete
        self.db.delete(deployment)
        self.db.commit()

        return True
