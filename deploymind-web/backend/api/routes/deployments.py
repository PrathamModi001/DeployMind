"""Deployment routes."""
from fastapi import APIRouter, Depends, HTTPException, status, Query, BackgroundTasks
from typing import Optional
from datetime import datetime
from sqlalchemy.orm import Session
import uuid

from ..schemas.deployment import (
    DeploymentCreate,
    DeploymentResponse,
    DeploymentListResponse,
    DeploymentStatus,
)
from ..middleware.auth import get_current_active_user
from ..services.database import get_db
from ..repositories.deployment_repo import DeploymentRepository
from ..services.deployment_service import DeploymentService

router = APIRouter(prefix="/api/deployments", tags=["Deployments"])


@router.get("", response_model=DeploymentListResponse)
async def list_deployments(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(10, ge=1, le=100, description="Items per page"),
    status: Optional[DeploymentStatus] = Query(None, description="Filter by status"),
    current_user: dict = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    List all deployments with pagination.

    Supports filtering by status and pagination.
    """
    repo = DeploymentRepository(db)

    # Calculate offset from page number
    offset = (page - 1) * page_size

    # Get deployments from database
    status_filter = status.value if status else None
    deployments, total = repo.list_deployments(
        offset=offset,
        limit=page_size,
        status=status_filter,
    )

    # Convert to response format
    deployment_responses = [
        _deployment_to_response(d) for d in deployments
    ]

    return DeploymentListResponse(
        total=total,
        page=page,
        page_size=page_size,
        deployments=deployment_responses,
    )


@router.get("/{deployment_id}", response_model=DeploymentResponse)
async def get_deployment(
    deployment_id: str,
    current_user: dict = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Get deployment details by ID.

    Returns full deployment information including status, logs, and metadata.
    """
    repo = DeploymentRepository(db)
    deployment = repo.get_by_id(deployment_id)

    if not deployment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Deployment {deployment_id} not found"
        )

    return _deployment_to_response(deployment)


@router.post("", response_model=DeploymentResponse, status_code=status.HTTP_201_CREATED)
async def create_deployment(
    deployment: DeploymentCreate,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Create a new deployment.

    Triggers the deployment pipeline in background:
    1. Security scanning
    2. Docker build
    3. EC2 deployment
    4. Health checks
    """
    # Generate deployment ID
    deployment_id = f"deploy-{uuid.uuid4().hex[:8]}"

    # Create deployment service
    service = DeploymentService(db)

    # Create new deployment in database
    new_deployment = service.create_deployment(
        deployment_id=deployment_id,
        repository=deployment.repository,
        instance_id=deployment.instance_id,
        user_id=current_user.get("user_id", 0),
        port=deployment.port,
        strategy=deployment.strategy,
        environment=deployment.environment,
        triggered_by=current_user.get("username", "unknown"),
    )

    # Trigger deployment workflow in background
    background_tasks.add_task(
        service.run_deployment_workflow,
        deployment_id
    )

    return _deployment_to_response(new_deployment)


@router.get("/{deployment_id}/logs")
async def get_deployment_logs(
    deployment_id: str,
    current_user: dict = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Get deployment logs.

    Returns streaming logs for the deployment process.
    """
    repo = DeploymentRepository(db)

    # Check if deployment exists
    deployment = repo.get_by_id(deployment_id)
    if not deployment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Deployment {deployment_id} not found"
        )

    # Get logs from database
    logs = repo.get_deployment_logs(deployment_id, limit=100)

    # Convert to response format
    log_responses = [
        {
            "timestamp": log.timestamp.isoformat(),
            "level": log.level,
            "message": log.message,
            "agent": log.agent,
        }
        for log in logs
    ]

    return {
        "deployment_id": deployment_id,
        "logs": log_responses,
    }


@router.post("/{deployment_id}/rollback", response_model=DeploymentResponse)
async def rollback_deployment(
    deployment_id: str,
    current_user: dict = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Rollback a deployment to previous version.

    Reverts to the last successful deployment.
    """
    repo = DeploymentRepository(db)
    deployment = repo.get_by_id(deployment_id)

    if not deployment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Deployment {deployment_id} not found"
        )

    # Update status to rolled_back
    updated_deployment = repo.update_status(deployment_id, "rolled_back")

    # TODO: Trigger actual rollback workflow in background

    return _deployment_to_response(updated_deployment)


def _deployment_to_response(deployment) -> DeploymentResponse:
    """Convert database Deployment model to API response schema."""
    # Extract port and environment from extra_data JSON field
    extra_data = deployment.extra_data or {}
    port = extra_data.get("port", 8080)
    environment = extra_data.get("environment", "production")

    # Map database status to API status enum
    status_map = {
        "pending": DeploymentStatus.PENDING,
        "security_scanning": DeploymentStatus.SECURITY_SCANNING,
        "security_failed": DeploymentStatus.FAILED,
        "building": DeploymentStatus.BUILDING,
        "build_failed": DeploymentStatus.FAILED,
        "deploying": DeploymentStatus.DEPLOYING,
        "deployed": DeploymentStatus.DEPLOYED,
        "failed": DeploymentStatus.FAILED,
        "rolling_back": DeploymentStatus.DEPLOYING,
        "rolled_back": DeploymentStatus.ROLLED_BACK,
    }

    api_status = status_map.get(deployment.status.value if hasattr(deployment.status, 'value') else deployment.status, DeploymentStatus.PENDING)

    return DeploymentResponse(
        id=deployment.id,
        repository=deployment.repository,
        instance_id=deployment.instance_id,
        commit_sha=deployment.commit_sha,
        status=api_status,
        image_tag=deployment.image_tag,
        port=port,
        strategy=deployment.strategy.value if hasattr(deployment.strategy, 'value') else deployment.strategy,
        environment=environment,
        created_at=deployment.created_at,
        updated_at=deployment.updated_at,
        duration_seconds=float(deployment.duration_seconds) if deployment.duration_seconds else None,
    )
