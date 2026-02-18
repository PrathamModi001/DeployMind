"""Security scanning endpoints."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any
import sys
from pathlib import Path

from api.middleware.auth import get_current_active_user
from api.services.security_service import SecurityService
from api.services.database import get_db

# Add deploymind-core to path
core_path = Path(__file__).parent.parent.parent.parent.parent / "deploymind-core"
sys.path.insert(0, str(core_path))

try:
    from deploymind.infrastructure.database.models import SecurityScan
    CORE_AVAILABLE = True
except ImportError:
    SecurityScan = None
    CORE_AVAILABLE = False

router = APIRouter(prefix="/api/security", tags=["security"])


class RepositoryScanRequest(BaseModel):
    """Request to scan repository."""
    repo_path: str


class ImageScanRequest(BaseModel):
    """Request to scan Docker image."""
    image_name: str


class ScanResultResponse(BaseModel):
    """Security scan result response."""
    id: int
    deployment_id: str
    scan_type: str
    passed: bool
    critical_count: int
    high_count: int
    medium_count: int
    low_count: int
    created_at: Any


@router.post("/deployments/{deployment_id}/scan/repository")
async def scan_repository(
    deployment_id: str,
    request: RepositoryScanRequest,
    current_user: dict = Depends(get_current_active_user)
):
    """
    Trigger repository security scan using Trivy.

    Args:
        deployment_id: ID of deployment to scan
        request: Scan request with repository path
        current_user: Authenticated user

    Returns:
        Scan results
    """
    service = SecurityService()
    result = await service.scan_repository(deployment_id, request.repo_path)
    return result


@router.post("/deployments/{deployment_id}/scan/image")
async def scan_image(
    deployment_id: str,
    request: ImageScanRequest,
    current_user: dict = Depends(get_current_active_user)
):
    """
    Trigger Docker image security scan using Trivy.

    Args:
        deployment_id: ID of deployment to scan
        request: Scan request with image name
        current_user: Authenticated user

    Returns:
        Scan results
    """
    service = SecurityService()
    result = await service.scan_docker_image(deployment_id, request.image_name)
    return result


@router.get("/deployments/{deployment_id}/scan/results")
async def get_scan_results(
    deployment_id: str,
    current_user: dict = Depends(get_current_active_user)
):
    """
    Get all security scan results for deployment.

    Args:
        deployment_id: ID of deployment
        current_user: Authenticated user

    Returns:
        List of scan results
    """
    if not CORE_AVAILABLE or not SecurityScan:
        # Return empty list if core not available
        return []

    db = next(get_db())
    scans = db.query(SecurityScan)\
        .filter(SecurityScan.deployment_id == deployment_id)\
        .all()

    return [
        {
            "id": scan.id,
            "deployment_id": scan.deployment_id,
            "scan_type": scan.scan_type,
            "passed": scan.passed,
            "critical_count": scan.critical_count,
            "high_count": scan.high_count,
            "medium_count": scan.medium_count,
            "low_count": scan.low_count,
            "created_at": getattr(scan, 'created_at', None) or getattr(scan, 'timestamp', None)
        }
        for scan in scans
    ]
