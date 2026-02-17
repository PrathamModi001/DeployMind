"""Security scan repository implementation.

Implements the SecurityScanRepository interface from the domain layer
using SQLAlchemy for persistence.
"""

from typing import List, Optional
from sqlalchemy.orm import Session

from deploymind.domain.repositories.security_scan_repository import SecurityScanRepository
from deploymind.infrastructure.database.models import SecurityScan as SecurityScanModel
from deploymind.infrastructure.database.connection import get_db_session


class SecurityScanRepositoryImpl(SecurityScanRepository):
    """SQLAlchemy implementation of SecurityScanRepository."""

    def __init__(self, db: Session = None):
        """Initialize repository with database session.

        Args:
            db: SQLAlchemy session. If None, creates a new session.
        """
        self.db = db or get_db_session()

    def create(self, deployment_id: str, scan_data: dict) -> dict:
        """Create a new security scan record.

        Args:
            deployment_id: Deployment ID this scan belongs to.
            scan_data: Security scan data dictionary.

        Returns:
            Created security scan data.
        """
        db_scan = SecurityScanModel(
            deployment_id=deployment_id,
            scan_type=scan_data.get('scan_type', 'filesystem'),
            scanner=scan_data.get('scanner', 'trivy'),
            scan_started_at=scan_data.get('scan_started_at'),
            scan_completed_at=scan_data.get('scan_completed_at'),
            scan_duration_seconds=scan_data.get('scan_duration_seconds'),
            passed=scan_data.get('passed', False),
            total_vulnerabilities=scan_data.get('total_vulnerabilities', 0),
            critical_count=scan_data.get('critical_count', 0),
            high_count=scan_data.get('high_count', 0),
            medium_count=scan_data.get('medium_count', 0),
            low_count=scan_data.get('low_count', 0),
            vulnerabilities=scan_data.get('vulnerabilities'),
            recommendations=scan_data.get('recommendations'),
            agent_decision=scan_data.get('agent_decision'),
            agent_reasoning=scan_data.get('agent_reasoning'),
            trivy_version=scan_data.get('trivy_version'),
            scan_output=scan_data.get('scan_output'),
        )

        self.db.add(db_scan)
        self.db.commit()
        self.db.refresh(db_scan)

        return self._to_dict(db_scan)

    def get_by_deployment(self, deployment_id: str) -> List[dict]:
        """Get all security scans for a deployment.

        Args:
            deployment_id: Deployment ID.

        Returns:
            List of security scan data dictionaries.
        """
        db_scans = self.db.query(SecurityScanModel).filter(
            SecurityScanModel.deployment_id == deployment_id
        ).order_by(SecurityScanModel.scan_started_at.desc()).all()

        return [self._to_dict(scan) for scan in db_scans]

    def get_by_id(self, scan_id: int) -> Optional[dict]:
        """Get security scan by ID.

        Args:
            scan_id: Security scan ID.

        Returns:
            Security scan data or None if not found.
        """
        db_scan = self.db.query(SecurityScanModel).filter(
            SecurityScanModel.id == scan_id
        ).first()

        return self._to_dict(db_scan) if db_scan else None

    def get_latest_for_deployment(self, deployment_id: str) -> Optional[dict]:
        """Get the most recent security scan for a deployment.

        Args:
            deployment_id: Deployment ID.

        Returns:
            Latest security scan data or None if not found.
        """
        db_scan = self.db.query(SecurityScanModel).filter(
            SecurityScanModel.deployment_id == deployment_id
        ).order_by(SecurityScanModel.scan_started_at.desc()).first()

        return self._to_dict(db_scan) if db_scan else None

    def _to_dict(self, db_scan: SecurityScanModel) -> dict:
        """Convert database model to dictionary.

        Args:
            db_scan: SQLAlchemy model instance.

        Returns:
            Security scan data dictionary.
        """
        return {
            'id': db_scan.id,
            'deployment_id': db_scan.deployment_id,
            'scan_type': db_scan.scan_type,
            'scanner': db_scan.scanner,
            'scan_started_at': db_scan.scan_started_at,
            'scan_completed_at': db_scan.scan_completed_at,
            'scan_duration_seconds': db_scan.scan_duration_seconds,
            'passed': db_scan.passed,
            'total_vulnerabilities': db_scan.total_vulnerabilities,
            'critical_count': db_scan.critical_count,
            'high_count': db_scan.high_count,
            'medium_count': db_scan.medium_count,
            'low_count': db_scan.low_count,
            'vulnerabilities': db_scan.vulnerabilities,
            'recommendations': db_scan.recommendations,
            'agent_decision': db_scan.agent_decision,
            'agent_reasoning': db_scan.agent_reasoning,
            'trivy_version': db_scan.trivy_version,
            'scan_output': db_scan.scan_output,
        }
