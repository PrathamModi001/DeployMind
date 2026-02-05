"""Deployment repository implementation.

Implements the DeploymentRepository interface from the domain layer
using SQLAlchemy for persistence.
"""

from typing import List, Optional
from sqlalchemy.orm import Session

from domain.repositories.deployment_repository import DeploymentRepository
from domain.entities.deployment import Deployment as DomainDeployment
from infrastructure.database.models import Deployment as DeploymentModel
from infrastructure.database.connection import get_db_session


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
        db_deployment = DeploymentModel(
            id=deployment.id,
            repository=deployment.repository,
            instance_id=deployment.instance_id,
            status=deployment.status,
            created_at=deployment.created_at,
            image_tag=deployment.image_tag,
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

        # Update fields
        db_deployment.status = deployment.status
        db_deployment.image_tag = deployment.image_tag
        db_deployment.updated_at = deployment.updated_at

        self.db.commit()
        self.db.refresh(db_deployment)

        return self._to_domain(db_deployment)

    def list_all(self) -> List[DomainDeployment]:
        """List all deployments.

        Returns:
            List of deployment entities.
        """
        db_deployments = self.db.query(DeploymentModel).all()
        return [self._to_domain(d) for d in db_deployments]

    def _to_domain(self, db_deployment: DeploymentModel) -> DomainDeployment:
        """Convert database model to domain entity.

        Args:
            db_deployment: SQLAlchemy model instance.

        Returns:
            Domain deployment entity.
        """
        return DomainDeployment(
            id=db_deployment.id,
            repository=db_deployment.repository,
            instance_id=db_deployment.instance_id,
            status=db_deployment.status,
            created_at=db_deployment.created_at,
            updated_at=db_deployment.updated_at,
            image_tag=db_deployment.image_tag,
        )
