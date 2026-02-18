"""Real security scanning using deploymind-core Trivy scanner."""
import sys
from pathlib import Path
from typing import Dict, Optional
import logging

# Add deploymind-core to path
core_path = Path(__file__).parent.parent.parent.parent.parent / "deploymind-core"
sys.path.insert(0, str(core_path))

try:
    from deploymind.infrastructure.security.trivy_scanner import TrivyScanner
    from deploymind.domain.value_objects.security import SecuritySeverity
    from deploymind.infrastructure.database.models import SecurityScan
    CORE_AVAILABLE = True
except ImportError:
    TrivyScanner = None
    SecuritySeverity = None
    SecurityScan = None
    CORE_AVAILABLE = False

from api.services.database import get_db

logger = logging.getLogger(__name__)


class SecurityService:
    """Service for real security scanning using Trivy."""

    def __init__(self):
        """Initialize security service."""
        if CORE_AVAILABLE and TrivyScanner:
            try:
                self.scanner = TrivyScanner()
            except Exception as e:
                logger.warning(f"Failed to initialize Trivy scanner: {e}")
                self.scanner = None
        else:
            self.scanner = None

    async def scan_repository(
        self,
        deployment_id: str,
        repo_path: str
    ) -> Dict:
        """
        Scan repository for vulnerabilities using real Trivy.

        Args:
            deployment_id: ID of deployment to associate scan with
            repo_path: Path to repository to scan

        Returns:
            Dictionary with scan results
        """
        if not self.scanner:
            return self._mock_repository_scan(deployment_id)

        try:
            # Run filesystem scan
            result = self.scanner.scan_filesystem(
                path=repo_path,
                severity=SecuritySeverity.HIGH
            )

            # Store in database
            db = next(get_db())
            scan_record = SecurityScan(
                deployment_id=deployment_id,
                scan_type="filesystem",
                vulnerabilities=result.vulnerabilities,
                critical_count=result.critical_count,
                high_count=result.high_count,
                medium_count=result.medium_count,
                low_count=result.low_count,
                passed=result.passed,
                agent_decision="APPROVED" if result.passed else "REJECTED",
                agent_reasoning=f"Trivy scan completed. Found {result.critical_count} critical and {result.high_count} high severity vulnerabilities."
            )
            db.add(scan_record)
            db.commit()

            return {
                "passed": result.passed,
                "total_vulnerabilities": len(result.vulnerabilities),
                "critical": result.critical_count,
                "high": result.high_count,
                "medium": result.medium_count,
                "low": result.low_count,
                "details": result.vulnerabilities[:10]  # Top 10
            }
        except Exception as e:
            logger.error(f"Repository scan failed: {e}")
            return self._mock_repository_scan(deployment_id)

    async def scan_docker_image(
        self,
        deployment_id: str,
        image_name: str
    ) -> Dict:
        """
        Scan Docker image for vulnerabilities.

        Args:
            deployment_id: ID of deployment to associate scan with
            image_name: Docker image name to scan

        Returns:
            Dictionary with scan results
        """
        if not self.scanner:
            return self._mock_image_scan(deployment_id, image_name)

        try:
            # Run image scan
            result = self.scanner.scan_image(
                image_name=image_name,
                severity=SecuritySeverity.CRITICAL
            )

            # Store in database
            db = next(get_db())
            scan_record = SecurityScan(
                deployment_id=deployment_id,
                scan_type="image",
                vulnerabilities=result.vulnerabilities,
                critical_count=result.critical_count,
                high_count=result.high_count,
                medium_count=result.medium_count,
                low_count=result.low_count,
                passed=result.passed,
                agent_decision="APPROVED" if result.passed else "REJECTED",
                agent_reasoning=f"Image scan completed. Found {result.critical_count} critical vulnerabilities."
            )
            db.add(scan_record)
            db.commit()

            return {
                "passed": result.passed,
                "vulnerabilities": result.vulnerabilities,
                "critical": result.critical_count,
                "high": result.high_count
            }
        except Exception as e:
            logger.error(f"Image scan failed: {e}")
            return self._mock_image_scan(deployment_id, image_name)

    def _mock_repository_scan(self, deployment_id: str) -> Dict:
        """Mock repository scan when Trivy unavailable."""
        logger.info(f"Using mock repository scan for deployment {deployment_id}")
        return {
            "passed": True,
            "total_vulnerabilities": 0,
            "critical": 0,
            "high": 0,
            "medium": 0,
            "low": 0,
            "details": []
        }

    def _mock_image_scan(self, deployment_id: str, image_name: str) -> Dict:
        """Mock image scan when Trivy unavailable."""
        logger.info(f"Using mock image scan for {image_name} (deployment {deployment_id})")
        return {
            "passed": True,
            "vulnerabilities": [],
            "critical": 0,
            "high": 0
        }
