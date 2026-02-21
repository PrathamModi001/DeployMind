"""API routes for executing AI-powered actionable recommendations."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Dict, Any

from ..middleware.auth import get_current_active_user
from ..services.database import get_db
from ..services.action_executor import ActionExecutor
from ..schemas.ai_actions import (
    ActionExecutionRequest,
    ActionExecutionResponse,
    ActionStatusResponse,
    ActionStatus,
    ActionType,
    ScaleInstanceParams,
    StopIdleDeploymentsParams,
    TriggerSecurityScanParams,
)

router = APIRouter(prefix="/api/ai/actions", tags=["AI Actions"])


@router.post("/execute/scale-instance", response_model=ActionExecutionResponse)
async def execute_scale_instance(
    request: ActionExecutionRequest,
    current_user: dict = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Execute instance scaling action.

    Scales an EC2 instance to a different type (vertical scaling).
    Requires confirmation due to downtime and cost impact.

    Process:
    1. Stop EC2 instance
    2. Modify instance type
    3. Start EC2 instance
    4. Wait for instance to be running

    Args:
        request: Action execution request with parameters
        current_user: Authenticated user
        db: Database session

    Returns:
        ActionExecutionResponse with execution ID for status polling
    """
    # Validate parameters
    try:
        params = ScaleInstanceParams(**request.parameters)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid parameters: {str(e)}"
        )

    # Check confirmation for destructive action
    if not request.confirmed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Confirmation required for instance scaling"
        )

    executor = ActionExecutor(db)
    user_id = current_user.get("id", 0)

    try:
        execution = await executor.execute_action(
            user_id=user_id,
            action_type="scale_instance",
            parameters=request.parameters
        )

        # Estimate completion time (2-3 minutes for instance scaling)
        from datetime import datetime, timedelta
        estimated_completion = datetime.utcnow() + timedelta(minutes=3)

        return ActionExecutionResponse(
            execution_id=execution.id,
            status=ActionStatus(execution.status.value),
            message=f"Scaling instance from {params.current_instance_type} to {params.target_instance_type}",
            estimated_completion_time=estimated_completion
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to execute scaling: {str(e)}"
        )


@router.post("/execute/stop-idle-deployments", response_model=ActionExecutionResponse)
async def execute_stop_idle_deployments(
    request: ActionExecutionRequest,
    current_user: dict = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Execute bulk stop of idle deployments.

    Stops EC2 instances for multiple idle deployments to save costs.
    Requires confirmation due to service interruption.

    Args:
        request: Action execution request with deployment IDs
        current_user: Authenticated user
        db: Database session

    Returns:
        ActionExecutionResponse with execution ID
    """
    # Validate parameters
    try:
        params = StopIdleDeploymentsParams(**request.parameters)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid parameters: {str(e)}"
        )

    # Check confirmation
    if not request.confirmed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Confirmation required for stopping deployments"
        )

    executor = ActionExecutor(db)
    user_id = current_user.get("id", 0)

    try:
        execution = await executor.execute_action(
            user_id=user_id,
            action_type="stop_idle_deployments",
            parameters=request.parameters
        )

        from datetime import datetime, timedelta
        estimated_completion = datetime.utcnow() + timedelta(minutes=2)

        return ActionExecutionResponse(
            execution_id=execution.id,
            status=ActionStatus(execution.status.value),
            message=f"Stopping {len(params.deployment_ids)} idle deployments",
            estimated_completion_time=estimated_completion
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to execute stop: {str(e)}"
        )


@router.post("/execute/trigger-security-scan", response_model=ActionExecutionResponse)
async def execute_trigger_security_scan(
    request: ActionExecutionRequest,
    current_user: dict = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Execute security scan on deployment.

    Runs Trivy security scan on deployment container image.
    This is a safe, read-only operation that doesn't require confirmation.

    Args:
        request: Action execution request with deployment ID
        current_user: Authenticated user
        db: Database session

    Returns:
        ActionExecutionResponse with execution ID
    """
    # Validate parameters
    try:
        params = TriggerSecurityScanParams(**request.parameters)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid parameters: {str(e)}"
        )

    executor = ActionExecutor(db)
    user_id = current_user.get("id", 0)

    try:
        execution = await executor.execute_action(
            user_id=user_id,
            action_type="trigger_security_scan",
            parameters=request.parameters
        )

        from datetime import datetime, timedelta
        estimated_completion = datetime.utcnow() + timedelta(minutes=5)

        return ActionExecutionResponse(
            execution_id=execution.id,
            status=ActionStatus(execution.status.value),
            message=f"Running security scan for deployment {params.deployment_id}",
            estimated_completion_time=estimated_completion
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to execute scan: {str(e)}"
        )


@router.get("/status/{execution_id}", response_model=ActionStatusResponse)
async def get_action_status(
    execution_id: str,
    current_user: dict = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get status of an action execution.

    Poll this endpoint to track action progress and get results
    when the action completes.

    Recommended polling interval: 2 seconds

    Args:
        execution_id: Execution ID from initial request
        current_user: Authenticated user
        db: Database session

    Returns:
        ActionStatusResponse with current status and progress
    """
    executor = ActionExecutor(db)
    execution = executor.get_execution_status(execution_id)

    if not execution:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Execution {execution_id} not found"
        )

    # Verify user owns this execution
    user_id = current_user.get("id", 0)
    if execution.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view this execution"
        )

    # Calculate current message
    if execution.status == ActionStatusResponse.COMPLETED:
        message = f"Action completed successfully in {execution.duration_seconds:.1f}s"
    elif execution.status == ActionStatusResponse.FAILED:
        message = f"Action failed: {execution.error_message}"
    elif execution.status == ActionStatusResponse.IN_PROGRESS:
        message = execution.current_step or "Processing..."
    else:
        message = "Action queued"

    return ActionStatusResponse(
        execution_id=execution.id,
        status=ActionStatus(execution.status.value),
        action_type=ActionType(execution.action_type.value),
        progress_percent=execution.progress_percent,
        message=message,
        result=execution.result,
        error_message=execution.error_message,
        created_at=execution.created_at,
        started_at=execution.started_at,
        completed_at=execution.completed_at,
        duration_seconds=execution.duration_seconds
    )
