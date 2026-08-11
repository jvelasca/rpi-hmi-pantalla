"""Routers de la API HMI.

Expone los routers:
- hmi_router: endpoints REST (LED, button, status, display)
- ws_router: endpoint WebSocket
"""

from backend.app.api.hmi import router as hmi_router
from backend.app.api.ws import router as ws_router

__all__ = ["hmi_router", "ws_router"]
