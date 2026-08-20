"""Notificacion de estado a systemd via sd_notify (AF_UNIX).

Implementa el protocolo sd_notify sin dependencias externas: lee
NOTIFY_SOCKET del entorno y envia mensajes de texto por un socket
datagrama UNIX. Si no corre bajo systemd (Windows/CI/dev) no hace nada.
"""

from __future__ import annotations

import logging
import os
import socket

logger = logging.getLogger(__name__)


def notify(state: str) -> bool:
    """Envia un mensaje a systemd por el socket NOTIFY_SOCKET.

    Si NOTIFY_SOCKET no esta definido en el entorno, retorna False sin
    error (no-op). Nunca lanza excepciones hacia fuera.
    """
    sock_path = os.environ.get("NOTIFY_SOCKET")
    if not sock_path:
        return False

    family = getattr(socket, "AF_UNIX", None)
    if family is None:
        logger.debug("AF_UNIX no disponible en esta plataforma")
        return False

    try:
        sock = socket.socket(family, socket.SOCK_DGRAM)
    except OSError:
        logger.exception("No se pudo crear el socket de notificacion systemd")
        return False

    try:
        sock.sendto(state.encode(), sock_path)
    except OSError:
        logger.exception("No se pudo notificar a systemd: %s", state)
        return False
    finally:
        sock.close()

    return True


def notify_ready() -> bool:
    """Notifica a systemd que el servicio esta listo."""
    return notify("READY=1")


def notify_watchdog() -> bool:
    """Notifica a systemd que el servicio sigue vivo (watchdog)."""
    return notify("WATCHDOG=1")


def notify_stopping() -> bool:
    """Notifica a systemd que el servicio se esta deteniendo."""
    return notify("STOPPING=1")


def notify_status(message: str) -> bool:
    """Notifica a systemd un mensaje de estado legible."""
    return notify(f"STATUS={message}")


def watchdog_interval_usec() -> int | None:
    """Devuelve la mitad de WATCHDOG_USEC, o None si no hay watchdog.

    systemd recomienda enviar WATCHDOG=1 a la mitad del intervalo
    configurado en WatchdogSec para evitar falsos reinicios.
    """
    raw = os.environ.get("WATCHDOG_USEC")
    if raw is None:
        return None
    try:
        usec = int(raw)
    except ValueError:
        logger.warning("WATCHDOG_USEC no es un entero valido: %s", raw)
        return None
    return usec // 2
