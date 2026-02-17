"""Deployment routes."""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import Optional
from datetime import datetime

from ..schemas.deployment import (
    DeploymentCreate,
    DeploymentResponse,
    DeploymentListResponse,
    DeploymentStatus,
)
from ..middleware.auth import get_current_active_user

router = APIRouter(prefix="/api/deployments", tags=["Deployments"])


# Mock deployments database (replace with real database later)
MOCK_DEPLOYMENTS = [
    {
        "id": "a8083a12",
        "repository": "PrathamModi001/DeployMind",
        "instance_id": "i-0183af174a8023c1e",
        "commit_sha": "fbc3f7d4",
        "status": DeploymentStatus.DEPLOYED,
        "image_tag": "prathammodi001-deploymind:fbc3f7d4",
        "port": 8080,
        "strategy": "rolling",
        "environment": "production",
        "created_at": "2026-02-14T13:52:11",
        "updated_at": "2026-02-14T14:00:13",
        "duration_seconds": 477.0,
    }
]


@router.get("", response_model=DeploymentListResponse)
async def list_deployments(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(10, ge=1, le=100, description="Items per page"),
    status: Optional[DeploymentStatus] = Query(None, description="Filter by status"),
    current_user: dict = Depends(get_current_active_user),
):
    """
    List all deployments with pagination.

    Supports filtering by status and pagination.
    """
    # Filter by status if provided
    deployments = MOCK_DEPLOYMENTS
    if status:
        deployments = [d for d in deployments if d["status"] == status]

    # Pagination
    total = len(deployments)
    start = (page - 1) * page_size
    end = start + page_size
    paginated_deployments = deployments[start:end]

    return DeploymentListResponse(
        total=total,
        page=page,
        page_size=page_size,
        deployments=paginated_deployments,
    )


@router.get("/{deployment_id}", response_model=DeploymentResponse)
async def get_deployment(
    deployment_id: str,
    current_user: dict = Depends(get_current_active_user),
):
    """
    Get deployment details by ID.

    Returns full deployment information including status, logs, and metadata.
    """
    # Find deployment
    deployment = next((d for d in MOCK_DEPLOYMENTS if d["id"] == deployment_id), None)

    if not deployment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Deployment {deployment_id} not found"
        )

    return deployment


@router.post("", response_model=DeploymentResponse, status_code=status.HTTP_201_CREATED)
async def create_deployment(
    deployment: DeploymentCreate,
    current_user: dict = Depends(get_current_active_user),
):
    """
    Create a new deployment.

    Triggers the deployment pipeline:
    1. Security scanning
    2. Docker build
    3. EC2 deployment
    4. Health checks
    """
    # Generate deployment ID
    import uuid
    deployment_id = uuid.uuid4().hex[:8]

    # Create new deployment
    new_deployment = {
        "id": deployment_id,
        "repository": deployment.repository,
        "instance_id": deployment.instance_id,
        "commit_sha": None,  # Will be updated during deployment
        "status": DeploymentStatus.PENDING,
        "image_tag": None,
        "port": deployment.port,
        "strategy": deployment.strategy,
        "environment": deployment.environment,
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": None,
        "duration_seconds": None,
    }

    MOCK_DEPLOYMENTS.insert(0, new_deployment)

    # TODO: Trigger actual deployment workflow in background
    # For now, just return the created deployment

    return new_deployment


@router.get("/{deployment_id}/logs")
async def get_deployment_logs(
    deployment_id: str,
    current_user: dict = Depends(get_current_active_user),
):
    """
    Get deployment logs.

    Returns streaming logs for the deployment process.
    """
    # Find deployment
    deployment = next((d for d in MOCK_DEPLOYMENTS if d["id"] == deployment_id), None)

    if not deployment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Deployment {deployment_id} not found"
        )

    # Mock logs (replace with real logs later)
    return {
        "deployment_id": deployment_id,
        "logs": [
            {"timestamp": "2026-02-14T13:52:11", "level": "INFO", "message": "Starting deployment"},
            {"timestamp": "2026-02-14T13:52:12", "level": "INFO", "message": "Cloning repository"},
            {"timestamp": "2026-02-14T13:52:14", "level": "INFO", "message": "Security scan passed"},
            {"timestamp": "2026-02-14T13:55:00", "level": "INFO", "message": "Docker build complete"},
            {"timestamp": "2026-02-14T14:00:13", "level": "INFO", "message": "Deployment successful"},
        ]
    }


@router.post("/{deployment_id}/rollback", response_model=DeploymentResponse)
async def rollback_deployment(
    deployment_id: str,
    current_user: dict = Depends(get_current_active_user),
):
    """
    Rollback a deployment to previous version.

    Reverts to the last successful deployment.
    """
    # Find deployment
    deployment = next((d for d in MOCK_DEPLOYMENTS if d["id"] == deployment_id), None)

    if not deployment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Deployment {deployment_id} not found"
        )

    # Update status
    deployment["status"] = DeploymentStatus.ROLLED_BACK
    deployment["updated_at"] = datetime.utcnow().isoformat()

    return deployment
