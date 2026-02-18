"""WebSocket routes for real-time deployment updates."""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query
from sqlalchemy.orm import Session
import logging

from ..websocket.manager import manager
from ..services.database import get_db
from ..repositories.deployment_repo import DeploymentRepository

logger = logging.getLogger(__name__)
router = APIRouter(tags=["WebSocket"])


@router.websocket("/ws/deployments/{deployment_id}")
async def deployment_updates(
    websocket: WebSocket,
    deployment_id: str,
    db: Session = Depends(get_db),
):
    """
    WebSocket endpoint for real-time deployment updates.

    Streams:
    - Status changes
    - Log messages
    - Progress updates

    Args:
        websocket: WebSocket connection
        deployment_id: Deployment ID to subscribe to
        db: Database session
    """
    # Connect WebSocket
    await manager.connect(websocket, deployment_id)

    try:
        # Verify deployment exists
        repo = DeploymentRepository(db)
        deployment = repo.get_by_id(deployment_id)

        if not deployment:
            await manager.send_personal_message(
                {"error": "Deployment not found"},
                websocket
            )
            await websocket.close()
            return

        # Send initial deployment state
        await manager.send_personal_message(
            {
                "type": "initial_state",
                "deployment_id": deployment_id,
                "status": deployment.status.value if hasattr(deployment.status, 'value') else deployment.status,
                "repository": deployment.repository,
            },
            websocket
        )

        # Keep connection alive and handle messages
        while True:
            # Wait for client messages (ping/pong for keepalive)
            data = await websocket.receive_text()

            # Echo back as keepalive
            await manager.send_personal_message(
                {"type": "pong", "data": data},
                websocket
            )

    except WebSocketDisconnect:
        manager.disconnect(websocket, deployment_id)
        logger.info(f"Client disconnected from deployment {deployment_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(websocket, deployment_id)


@router.websocket("/ws/logs/{deployment_id}")
async def deployment_logs_stream(
    websocket: WebSocket,
    deployment_id: str,
    db: Session = Depends(get_db),
):
    """
    WebSocket endpoint for real-time log streaming.

    Streams deployment logs as they are created.

    Args:
        websocket: WebSocket connection
        deployment_id: Deployment ID
        db: Database session
    """
    await manager.connect(websocket, deployment_id)

    try:
        # Verify deployment exists
        repo = DeploymentRepository(db)
        deployment = repo.get_by_id(deployment_id)

        if not deployment:
            await manager.send_personal_message(
                {"error": "Deployment not found"},
                websocket
            )
            await websocket.close()
            return

        # Send existing logs
        logs = repo.get_deployment_logs(deployment_id, limit=100)
        for log in logs:
            await manager.send_personal_message(
                {
                    "type": "log",
                    "timestamp": log.timestamp.isoformat(),
                    "level": log.level,
                    "message": log.message,
                    "agent": log.agent,
                },
                websocket
            )

        # Keep connection alive for new logs
        while True:
            data = await websocket.receive_text()
            await manager.send_personal_message(
                {"type": "pong"},
                websocket
            )

    except WebSocketDisconnect:
        manager.disconnect(websocket, deployment_id)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(websocket, deployment_id)
