"""WebSocket connection manager for real-time updates."""
from typing import Dict, List
from fastapi import WebSocket
import logging

logger = logging.getLogger(__name__)


class WebSocketManager:
    """Manages WebSocket connections for real-time deployment updates."""

    def __init__(self):
        """Initialize connection manager."""
        self.active_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, deployment_id: str):
        """
        Accept and register a new WebSocket connection.

        Args:
            websocket: WebSocket instance
            deployment_id: Deployment ID to subscribe to
        """
        await websocket.accept()

        if deployment_id not in self.active_connections:
            self.active_connections[deployment_id] = []

        self.active_connections[deployment_id].append(websocket)
        logger.info(f"WebSocket connected for deployment {deployment_id}")

    def disconnect(self, websocket: WebSocket, deployment_id: str):
        """
        Remove a WebSocket connection.

        Args:
            websocket: WebSocket instance to disconnect
            deployment_id: Deployment ID
        """
        if deployment_id in self.active_connections:
            if websocket in self.active_connections[deployment_id]:
                self.active_connections[deployment_id].remove(websocket)
                logger.info(f"WebSocket disconnected from deployment {deployment_id}")

            # Clean up empty lists
            if not self.active_connections[deployment_id]:
                del self.active_connections[deployment_id]

    async def send_personal_message(self, message: dict, websocket: WebSocket):
        """
        Send message to a specific WebSocket.

        Args:
            message: Message to send (will be JSON serialized)
            websocket: WebSocket to send to
        """
        await websocket.send_json(message)

    async def broadcast(self, deployment_id: str, message: dict):
        """
        Broadcast message to all connections for a deployment.

        Args:
            deployment_id: Deployment ID
            message: Message to broadcast (will be JSON serialized)
        """
        if deployment_id in self.active_connections:
            disconnected = []

            for websocket in self.active_connections[deployment_id]:
                try:
                    await websocket.send_json(message)
                except Exception as e:
                    logger.error(f"Error broadcasting to WebSocket: {e}")
                    disconnected.append(websocket)

            # Remove disconnected websockets
            for ws in disconnected:
                self.disconnect(ws, deployment_id)


# Global WebSocket manager instance
manager = WebSocketManager()
