"""Routers de la API.

Expone los routers:
- hmi_router: endpoints REST HMI (LED, button, status, display)
- ws_router: endpoint WebSocket
- admin_ssh_router: endpoints administrativos SSH (/admin/ssh/*)
- admin_deploy_router: endpoints administrativos de deploy (/admin/deploy/*)
"""

from backend.app.api.hmi import router as hmi_router
from backend.app.api.ws import router as ws_router
from backend.app.api.ssh import router as admin_ssh_router
from backend.app.api.deploy import router as admin_deploy_router

__all__ = ["hmi_router", "ws_router", "admin_ssh_router", "admin_deploy_router"]
