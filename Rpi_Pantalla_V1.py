"""
Rpi_Pantalla_V1 — Punto de entrada legacy
==========================================

Wrapper de compatibilidad que delega en el entry point canonico
`backend.app.main`. Conservado por retrocompatibilidad con
scripts y documentacion existente.

    Uso:
        python Rpi_Pantalla_V1.py
        python Rpi_Pantalla_V1.py --port 8080
        python Rpi_Pantalla_V1.py --host 0.0.0.0 --port 8000 --reload

Entry point canonico:
    python -m backend.app.main
    uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
"""
from __future__ import annotations

import argparse
import logging
import sys

import uvicorn

from backend.app.config import settings
from backend.app.main import app

logger = logging.getLogger("rpi_pantalla.main")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Raspberry HMI Backend — Plataforma industrial escalable",
    )
    parser.add_argument("--host", type=str, default=settings.backend_host,
                        help=f"Direccion de escucha (default: {settings.backend_host})")
    parser.add_argument("--port", type=int, default=settings.backend_port,
                        help=f"Puerto de escucha (default: {settings.backend_port})")
    parser.add_argument("--reload", action="store_true", default=False,
                        help="Activar auto-reload para desarrollo")
    parser.add_argument("--log-level", type=str, default=settings.log_level,
                        choices=["debug", "info", "warning", "error", "critical"],
                        help=f"Nivel de logging (default: {settings.log_level})")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    log_level = getattr(logging, args.log_level.upper(), logging.INFO)
    logging.getLogger().setLevel(log_level)

    logger.info(
        "Iniciando Raspberry HMI Backend en %s:%d (reload=%s)",
        args.host, args.port, args.reload,
    )

    try:
        uvicorn.run(
            app,
            host=args.host,
            port=args.port,
            reload=args.reload,
            log_level=args.log_level,
        )
    except KeyboardInterrupt:
        logger.info("Servidor detenido por el usuario")
        sys.exit(0)
    except Exception:
        logger.exception("Error fatal al iniciar el servidor")
        sys.exit(1)


if __name__ == "__main__":
    main()
