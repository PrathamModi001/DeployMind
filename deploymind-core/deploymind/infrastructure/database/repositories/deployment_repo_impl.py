"""Deployment repository implementation.

Implements the DeploymentRepository interface from the domain layer
using SQLAlchemy for persistence.
"""

from typing import List, Optional
from sqlalchemy.orm import Session

from deploymind.domain.repositories.deployment_repository import DeploymentRepository
from deploymind.domain.entities.deployment import Deployment as DomainDeployment
from deploymind.infrastructure.database.models import Deployment as DeploymentModel
from deploymind.infrastructure.database.connection import get_db_session


class DeploymentRepositoryImpl(DeploymentRepository):
    """SQLAlchemy implementation of DeploymentRepository."""

    def __init__(self, db: Session = None):
        """Initialize repository with database session.

        Args:
            db: SQLAlchemy session. If None, creates a new session.
        """
        self.db = db or get_db_session()

    def create(self, deployment: DomainDeployment) -> DomainDeployment:
        """Create a new deployment.

        Args:
            deployment: Domain deployment entity.

        Returns:
            Created deployment entity.
        """
        # Convert domain entity to database model with all fields
        db_deployment = DeploymentModel(
            id=deployment.id,
            repository=deployment.repository,
            instance_id=deployment.instance_id,
            status=deployment.status,
            created_at=deployment.created_at,
            updated_at=deployment.updated_at,
            image_tag=deployment.image_tag,
            # Additional fields from domain entity (if present)
            commit_sha=getattr(deployment, 'commit_sha', None),
            branch=getattr(deployment, 'branch', 'main'),
            region=getattr(deployment, 'region', 'us-east-1'),
            strategy=getattr(deployment, 'strategy', 'rolling'),
            image_size_mb=getattr(deployment, 'image_size_mb', None),
            started_at=getattr(deployment, 'started_at', None),
            completed_at=getattr(deployment, 'completed_at', None),
            duration_seconds=getattr(deployment, 'duration_seconds', None),
            triggered_by=getattr(deployment, 'triggered_by', 'manual'),
            trigger_type=getattr(deployment, 'trigger_type', 'manual'),
            previous_deployment_id=getattr(deployment, 'previous_deployment_id', None),
            rollback_reason=getattr(deployment, 'rollback_reason', None),
            extra_data=getattr(deployment, 'extra_data', None),
        )

        self.db.add(db_deployment)
        self.db.commit()
        self.db.refresh(db_deployment)

        return self._to_domain(db_deployment)

    def get_by_id(self, deployment_id: str) -> Optional[DomainDeployment]:
        """Get deployment by ID.

        Args:
            deployment_id: Deployment ID.

        Returns:
            Deployment entity or None if not found.
        """
        db_deployment = self.db.query(DeploymentModel).filter(
            DeploymentModel.id == deployment_id
        ).first()

        return self._to_domain(db_deployment) if db_deployment else None

    def update(self, deployment: DomainDeployment) -> DomainDeployment:
        """Update existing deployment.

        Args:
            deployment: Domain deployment entity with updated data.

        Returns:
            Updated deployment entity.
        """
        db_deployment = self.db.query(DeploymentModel).filter(
            DeploymentModel.id == deployment.id
        ).first()

        if not db_deployment:
            raise ValueError(f"Deployment {deployment.id} not found")

        # Update all modifiable fields
        db_deployment.status = deployment.status
        db_deployment.image_tag = deployment.image_tag
        db_deployment.updated_at = deployment.updated_at

        # Update additional fields if present
        if hasattr(deployment, 'commit_sha'):
            db_deployment.commit_sha = deployment.commit_sha
        if hasattr(deployment, 'image_size_mb'):
            db_deployment.image_size_mb = deployment.image_size_mb
        if hasattr(deployment, 'started_at'):
            db_deployment.started_at = deployment.started_at
        if hasattr(deployment, 'completed_at'):
            db_deployment.completed_at = deployment.completed_at
        if hasattr(deployment, 'duration_seconds'):
            db_deployment.duration_seconds = deployment.duration_seconds
        if hasattr(deployment, 'rollback_reason'):
            db_deployment.rollback_reason = deployment.rollback_reason
        if hasattr(deployment, 'extra_data'):
            db_deployment.extra_data = deployment.extra_data

        self.db.commit()
        self.db.refresh(db_deployment)

        return self._to_domain(db_deployment)

    def list_all(self, limit: Optional[int] = None, offset: int = 0) -> List[DomainDeployment]:
        """List all deployments ordered by creation time (newest first).

        Args:
            limit: Maximum number of deployments to return.
            offset: Number of deployments to skip.

        Returns:
            List of deployment entities.
        """
        query = self.db.query(DeploymentModel).order_by(DeploymentModel.created_at.desc())

        if offset > 0:
            query = query.offset(offset)
        if limit:
            query = query.limit(limit)

        db_deployments = query.all()
        return [self._to_domain(d) for d in db_deployments]

    def get_by_repository(self, repository: str, limit: int = 10) -> List[DomainDeployment]:
        """Get deployments for a specific repository.

        Args:
            repository: Repository name (e.g., 'owner/repo').
            limit: Maximum number of deployments to return.

        Returns:
            List of deployment entities for the repository.
        """
        db_deployments = self.db.query(DeploymentModel).filter(
            DeploymentModel.repository == repository
        ).order_by(DeploymentModel.created_at.desc()).limit(limit).all()

        return [self._to_domain(d) for d in db_deployments]

    def get_by_status(self, status: str, limit: int = 10) -> List[DomainDeployment]:
        """Get deployments by status.

        Args:
            status: Deployment status (e.g., 'deployed', 'failed').
            limit: Maximum number of deployments to return.

        Returns:
            List of deployment entities with the given status.
        """
        db_deployments = self.db.query(DeploymentModel).filter(
            DeploymentModel.status == status
        ).order_by(DeploymentModel.created_at.desc()).limit(limit).all()

        return [self._to_domain(d) for d in db_deployments]

    def get_recent(self, limit: int = 10) -> List[DomainDeployment]:
        """Get most recent deployments.

        Args:
            limit: Maximum number of deployments to return.

        Returns:
            List of most recent deployment entities.
        """
        return self.list_all(limit=limit)

    def count(self) -> int:
        """Get total count of deployments.

        Returns:
            Total number of deployments.
        """
        return self.db.query(DeploymentModel).count()

    def delete(self, deployment_id: str) -> bool:
        """Delete a deployment.

        Args:
            deployment_id: Deployment ID to delete.

        Returns:
            True if deleted, False if not found.
        """
        db_deployment = self.db.query(DeploymentModel).filter(
            DeploymentModel.id == deployment_id
        ).first()

        if not db_deployment:
            return False

        self.db.delete(db_deployment)
        self.db.commit()
        return True

    def _to_domain(self, db_deployment: DeploymentModel) -> DomainDeployment:
        """Convert database model to domain entity.

        Args:
            db_deployment: SQLAlchemy model instance.

        Returns:
            Domain deployment entity.
        """
        # Create deployment with required fields
        deployment = DomainDeployment(
            id=db_deployment.id,
            repository=db_deployment.repository,
            instance_id=db_deployment.instance_id,
            status=db_deployment.status,
            created_at=db_deployment.created_at,
            updated_at=db_deployment.updated_at,
            image_tag=db_deployment.image_tag,
        )

        # Add optional fields as attributes
        deployment.commit_sha = db_deployment.commit_sha
        deployment.branch = db_deployment.branch
        deployment.region = db_deployment.region
        deployment.strategy = db_deployment.strategy
        deployment.image_size_mb = db_deployment.image_size_mb
        deployment.started_at = db_deployment.started_at
        deployment.completed_at = db_deployment.completed_at
        deployment.duration_seconds = db_deployment.duration_seconds
        deployment.triggered_by = db_deployment.triggered_by
        deployment.trigger_type = db_deployment.trigger_type
        deployment.previous_deployment_id = db_deployment.previous_deployment_id
        deployment.rollback_reason = db_deployment.rollback_reason
        deployment.extra_data = db_deployment.extra_data

        return deployment
