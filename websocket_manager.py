"""WebSocket connection manager for real-time updates."""
import logging
from typing import Dict, Set

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages WebSocket connections per form."""
    
    def __init__(self):
        # form_id -> set of WebSocket connections
        self.active_connections: Dict[int, Set[WebSocket]] = {}
    
    async def connect(self, websocket: WebSocket, form_id: int):
        """Connect a WebSocket for a specific form."""
        await websocket.accept()
        if form_id not in self.active_connections:
            self.active_connections[form_id] = set()
        self.active_connections[form_id].add(websocket)
        logger.info(f"WebSocket connected for form {form_id}. Total connections: {len(self.active_connections[form_id])}")
    
    def disconnect(self, websocket: WebSocket, form_id: int):
        """Disconnect a WebSocket."""
        if form_id in self.active_connections:
            self.active_connections[form_id].discard(websocket)
            if not self.active_connections[form_id]:
                del self.active_connections[form_id]
        logger.info(f"WebSocket disconnected for form {form_id}")
    
    async def broadcast_to_form(self, form_id: int, message: dict):
        """Broadcast a message to all connections for a specific form."""
        if form_id in self.active_connections:
            disconnected = set()
            for connection in self.active_connections[form_id]:
                try:
                    await connection.send_json(message)
                except Exception as e:
                    logger.error(f"Error sending message to WebSocket: {e}")
                    disconnected.add(connection)
            
            # Remove disconnected connections
            for conn in disconnected:
                self.active_connections[form_id].discard(conn)


# Global connection manager instance
manager = ConnectionManager()

