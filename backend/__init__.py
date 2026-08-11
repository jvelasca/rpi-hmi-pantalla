"""Backend FastAPI para RPi HMI — Panel de control industrial.

Paquete principal que expone la aplicacion FastAPI lista para
ser servida por uvicorn.

Uso:
    uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
"""

from backend.app.main import app

__all__ = ["app"]
