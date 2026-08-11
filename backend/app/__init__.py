"""Paquete `backend.app` — nucleo de la aplicacion FastAPI.

Expone la instancia `app` lista para ser servida por uvicorn.
"""

from backend.app.main import app

__all__ = ["app"]
