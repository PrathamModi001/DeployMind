"""Build result repository implementation.

Implements the BuildResultRepository interface from the domain layer
using SQLAlchemy for persistence.
"""

from typing import List, Optional
from sqlalchemy.orm import Session

from deploymind.domain.repositories.build_result_repository import BuildResultRepository
from deploymind.infrastructure.database.models import BuildResult as BuildResultModel
from deploymind.infrastructure.database.connection import get_db_session


class BuildResultRepositoryImpl(BuildResultRepository):
    """SQLAlchemy implementation of BuildResultRepository."""

    def __init__(self, db: Session = None):
        """Initialize repository with database session.

        Args:
            db: SQLAlchemy session. If None, creates a new session.
        """
        self.db = db or get_db_session()

    def create(self, deployment_id: str, build_data: dict) -> dict:
        """Create a new build result record.

        Args:
            deployment_id: Deployment ID this build belongs to.
            build_data: Build result data dictionary.

        Returns:
            Created build result data.
        """
        db_build = BuildResultModel(
            deployment_id=deployment_id,
            build_started_at=build_data.get('build_started_at'),
            build_completed_at=build_data.get('build_completed_at'),
            build_duration_seconds=build_data.get('build_duration_seconds'),
            success=build_data.get('success', False),
            exit_code=build_data.get('exit_code'),
            dockerfile_path=build_data.get('dockerfile_path', 'Dockerfile'),
            dockerfile_generated=build_data.get('dockerfile_generated', False),
            detected_language=build_data.get('detected_language'),
            detected_framework=build_data.get('detected_framework'),
            image_id=build_data.get('image_id'),
            image_tag=build_data.get('image_tag'),
            image_size_bytes=build_data.get('image_size_bytes'),
            layer_count=build_data.get('layer_count'),
            optimizations_applied=build_data.get('optimizations_applied'),
            original_size_bytes=build_data.get('original_size_bytes'),
            optimized_size_bytes=build_data.get('optimized_size_bytes'),
            size_reduction_percent=build_data.get('size_reduction_percent'),
            build_log=build_data.get('build_log'),
            error_message=build_data.get('error_message'),
            agent_suggestions=build_data.get('agent_suggestions'),
        )

        self.db.add(db_build)
        self.db.commit()
        self.db.refresh(db_build)

        return self._to_dict(db_build)

    def get_by_deployment(self, deployment_id: str) -> List[dict]:
        """Get all build results for a deployment.

        Args:
            deployment_id: Deployment ID.

        Returns:
            List of build result data dictionaries.
        """
        db_builds = self.db.query(BuildResultModel).filter(
            BuildResultModel.deployment_id == deployment_id
        ).order_by(BuildResultModel.build_started_at.desc()).all()

        return [self._to_dict(build) for build in db_builds]

    def get_by_id(self, build_id: int) -> Optional[dict]:
        """Get build result by ID.

        Args:
            build_id: Build result ID.

        Returns:
            Build result data or None if not found.
        """
        db_build = self.db.query(BuildResultModel).filter(
            BuildResultModel.id == build_id
        ).first()

        return self._to_dict(db_build) if db_build else None

    def get_latest_for_deployment(self, deployment_id: str) -> Optional[dict]:
        """Get the most recent build result for a deployment.

        Args:
            deployment_id: Deployment ID.

        Returns:
            Latest build result data or None if not found.
        """
        db_build = self.db.query(BuildResultModel).filter(
            BuildResultModel.deployment_id == deployment_id
        ).order_by(BuildResultModel.build_started_at.desc()).first()

        return self._to_dict(db_build) if db_build else None

    def _to_dict(self, db_build: BuildResultModel) -> dict:
        """Convert database model to dictionary.

        Args:
            db_build: SQLAlchemy model instance.

        Returns:
            Build result data dictionary.
        """
        return {
            'id': db_build.id,
            'deployment_id': db_build.deployment_id,
            'build_started_at': db_build.build_started_at,
            'build_completed_at': db_build.build_completed_at,
            'build_duration_seconds': db_build.build_duration_seconds,
            'success': db_build.success,
            'exit_code': db_build.exit_code,
            'dockerfile_path': db_build.dockerfile_path,
            'dockerfile_generated': db_build.dockerfile_generated,
            'detected_language': db_build.detected_language,
            'detected_framework': db_build.detected_framework,
            'image_id': db_build.image_id,
            'image_tag': db_build.image_tag,
            'image_size_bytes': db_build.image_size_bytes,
            'layer_count': db_build.layer_count,
            'optimizations_applied': db_build.optimizations_applied,
            'original_size_bytes': db_build.original_size_bytes,
            'optimized_size_bytes': db_build.optimized_size_bytes,
            'size_reduction_percent': db_build.size_reduction_percent,
            'build_log': db_build.build_log,
            'error_message': db_build.error_message,
            'agent_suggestions': db_build.agent_suggestions,
        }
