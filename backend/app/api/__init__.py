"""Routers de la API.

Expone los routers:
- auth_router: endpoints de autenticacion del panel web (/api/auth/*)
- hmi_router: endpoints REST HMI (LED, button, status, display)
- ws_router: endpoint WebSocket
- health_router: endpoint health check (/health)
- admin_ssh_router: endpoints administrativos SSH (/admin/ssh/*)
- admin_deploy_router: endpoints administrativos de deploy (/admin/deploy/*)
"""

from backend.app.api.auth import router as auth_router
from backend.app.api.deploy import router as admin_deploy_router
from backend.app.api.health import router as health_router
from backend.app.api.hmi import router as hmi_router
from backend.app.api.network import router as network_router
from backend.app.api.ssh import router as admin_ssh_router
from backend.app.api.ws import router as ws_router

__all__ = [
    "auth_router",
    "hmi_router",
    "ws_router",
    "health_router",
    "network_router",
    "admin_ssh_router",
    "admin_deploy_router",
]
