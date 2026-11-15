"""WebSocket management for real-time updates.

This module provides WebSocket connection management for pushing
real-time updates to connected clients.
"""

from app.ws.manager import ConnectionManager, ws_manager

__all__ = ["ConnectionManager", "ws_manager"]
