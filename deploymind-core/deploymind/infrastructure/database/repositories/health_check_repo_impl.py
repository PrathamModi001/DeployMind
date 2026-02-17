"""Health check repository implementation.

Implements the HealthCheckRepository interface from the domain layer
using SQLAlchemy for persistence.
"""

from typing import List, Optional
from sqlalchemy.orm import Session

from deploymind.domain.repositories.health_check_repository import HealthCheckRepository
from deploymind.infrastructure.database.models import HealthCheck as HealthCheckModel
from deploymind.infrastructure.database.connection import get_db_session


class HealthCheckRepositoryImpl(HealthCheckRepository):
    """SQLAlchemy implementation of HealthCheckRepository."""

    def __init__(self, db: Session = None):
        """Initialize repository with database session.

        Args:
            db: SQLAlchemy session. If None, creates a new session.
        """
        self.db = db or get_db_session()

    def create(self, deployment_id: str, check_data: dict) -> dict:
        """Create a new health check record.

        Args:
            deployment_id: Deployment ID this check belongs to.
            check_data: Health check data dictionary.

        Returns:
            Created health check data.
        """
        db_check = HealthCheckModel(
            deployment_id=deployment_id,
            check_type=check_data.get('check_type', 'http'),
            check_url=check_data.get('check_url'),
            healthy=check_data.get('healthy', False),
            status_code=check_data.get('status_code'),
            response_time_ms=check_data.get('response_time_ms'),
            error_message=check_data.get('error_message'),
            check_time=check_data.get('check_time'),
            attempt_number=check_data.get('attempt_number', 1),
            max_attempts=check_data.get('max_attempts', 5),
            response_body=check_data.get('response_body'),
            instance_state=check_data.get('instance_state'),
            instance_status=check_data.get('instance_status'),
        )

        self.db.add(db_check)
        self.db.commit()
        self.db.refresh(db_check)

        return self._to_dict(db_check)

    def get_by_deployment(self, deployment_id: str) -> List[dict]:
        """Get all health checks for a deployment.

        Args:
            deployment_id: Deployment ID.

        Returns:
            List of health check data dictionaries.
        """
        db_checks = self.db.query(HealthCheckModel).filter(
            HealthCheckModel.deployment_id == deployment_id
        ).order_by(HealthCheckModel.check_time.desc()).all()

        return [self._to_dict(check) for check in db_checks]

    def get_by_id(self, check_id: int) -> Optional[dict]:
        """Get health check by ID.

        Args:
            check_id: Health check ID.

        Returns:
            Health check data or None if not found.
        """
        db_check = self.db.query(HealthCheckModel).filter(
            HealthCheckModel.id == check_id
        ).first()

        return self._to_dict(db_check) if db_check else None

    def get_latest_for_deployment(self, deployment_id: str) -> Optional[dict]:
        """Get the most recent health check for a deployment.

        Args:
            deployment_id: Deployment ID.

        Returns:
            Latest health check data or None if not found.
        """
        db_check = self.db.query(HealthCheckModel).filter(
            HealthCheckModel.deployment_id == deployment_id
        ).order_by(HealthCheckModel.check_time.desc()).first()

        return self._to_dict(db_check) if db_check else None

    def get_failed_checks(self, deployment_id: str) -> List[dict]:
        """Get all failed health checks for a deployment.

        Args:
            deployment_id: Deployment ID.

        Returns:
            List of failed health check data dictionaries.
        """
        db_checks = self.db.query(HealthCheckModel).filter(
            HealthCheckModel.deployment_id == deployment_id,
            HealthCheckModel.healthy == False
        ).order_by(HealthCheckModel.check_time.desc()).all()

        return [self._to_dict(check) for check in db_checks]

    def _to_dict(self, db_check: HealthCheckModel) -> dict:
        """Convert database model to dictionary.

        Args:
            db_check: SQLAlchemy model instance.

        Returns:
            Health check data dictionary.
        """
        return {
            'id': db_check.id,
            'deployment_id': db_check.deployment_id,
            'check_type': db_check.check_type,
            'check_url': db_check.check_url,
            'healthy': db_check.healthy,
            'status_code': db_check.status_code,
            'response_time_ms': db_check.response_time_ms,
            'error_message': db_check.error_message,
            'check_time': db_check.check_time,
            'attempt_number': db_check.attempt_number,
            'max_attempts': db_check.max_attempts,
            'response_body': db_check.response_body,
            'instance_state': db_check.instance_state,
            'instance_status': db_check.instance_status,
        }
