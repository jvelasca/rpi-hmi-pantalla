"""
Rpi_Pantalla_V1 — Punto de entrada principal
==============================================

Arranca el servidor FastAPI con uvicorn, cargando la configuración
desde variables de entorno (.env) y exponiendo la API REST en el
puerto configurado.

    Uso:
        python Rpi_Pantalla_V1.py
        python Rpi_Pantalla_V1.py --port 8080
        python Rpi_Pantalla_V1.py --host 0.0.0.0 --port 8000

    Endpoints principales:
        /health          — Health check del backend local
        /docs            — Documentación OpenAPI (Swagger)
        /api/ssh/*       — Gestión de conexión SSH a la Pi
        /api/deploy/*    — Despliegue remoto de la app en la Pi
"""
from __future__ import annotations

import argparse
import logging
import sys

import uvicorn

logger = logging.getLogger("rpi_pantalla.main")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


def parse_args() -> argparse.Namespace:
    """Parsea los argumentos de línea de comandos.

    Returns:
        Namespace con host, port, reload y log-level.
    """
    parser = argparse.ArgumentParser(
        description="Raspberry HMI Backend — Plataforma industrial escalable",
    )
    parser.add_argument(
        "--host",
        type=str,
        default="0.0.0.0",
        help="Dirección de escucha (default: 0.0.0.0)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Puerto de escucha (default: 8000)",
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        default=False,
        help="Activar auto-reload para desarrollo",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="info",
        choices=["debug", "info", "warning", "error", "critical"],
        help="Nivel de logging (default: info)",
    )
    return parser.parse_args()


def main() -> None:
    """Función principal — arranca el servidor uvicorn."""
    args = parse_args()

    # Ajustar nivel de logging global
    log_level = getattr(logging, args.log_level.upper(), logging.INFO)
    logging.getLogger().setLevel(log_level)

    logger.info(
        "Iniciando Raspberry HMI Backend en %s:%d (reload=%s)",
        args.host,
        args.port,
        args.reload,
    )
    logger.info("Documentación API: http://%s:%d/docs", args.host, args.port)
    logger.info("Health check: http://%s:%d/health", args.host, args.port)

    try:
        uvicorn.run(
            "backend.app.main:app",
            host=args.host,
            port=args.port,
            reload=args.reload,
            log_level=args.log_level,
        )
    except KeyboardInterrupt:
        logger.info("Servidor detenido por el usuario")
        sys.exit(0)
    except Exception as exc:
        logger.exception("Error fatal al iniciar el servidor")
        sys.exit(1)


if __name__ == "__main__":
    main()
