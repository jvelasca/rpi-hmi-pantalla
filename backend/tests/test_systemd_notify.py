"""Tests para el modulo systemd_notify (sd_notify via AF_UNIX).

No dependen de systemd: simulan NOTIFY_SOCKET con monkeypatch y
mockean socket.socket para no abrir sockets reales. Como AF_UNIX no
existe en Windows, se inyecta un valor ficticio en el atributo para
que notify() recorra la ruta de envio.
"""

from __future__ import annotations

from unittest.mock import patch

from backend.app.services import systemd_notify
from backend.app.services.systemd_notify import (
    notify,
    notify_ready,
    notify_stopping,
    notify_watchdog,
    watchdog_interval_usec,
)

SOCK_PATH = "/run/systemd/notify"


def test_notify_returns_false_without_notify_socket(monkeypatch):
    """Sin NOTIFY_SOCKET, notify() es un no-op que retorna False."""
    monkeypatch.delenv("NOTIFY_SOCKET", raising=False)

    assert notify("READY=1") is False


def test_watchdog_interval_none_without_env(monkeypatch):
    """Sin WATCHDOG_USEC, watchdog_interval_usec() retorna None."""
    monkeypatch.delenv("WATCHDOG_USEC", raising=False)

    assert watchdog_interval_usec() is None


def test_watchdog_interval_half_of_watchdog_usec(monkeypatch):
    """Con WATCHDOG_USEC=30000000 (30s), retorna la mitad (15000000)."""
    monkeypatch.setenv("WATCHDOG_USEC", "30000000")

    assert watchdog_interval_usec() == 15000000


def test_notify_ready_sends_ready_byte(monkeypatch):
    """notify_ready() envia b"READY=1" por el socket NOTIFY_SOCKET."""
    monkeypatch.setenv("NOTIFY_SOCKET", SOCK_PATH)

    with patch.object(systemd_notify.socket, "AF_UNIX", 1, create=True), \
         patch.object(systemd_notify.socket, "socket") as mock_socket_cls:
        mock_sock = mock_socket_cls.return_value
        result = notify_ready()

    assert result is True
    mock_socket_cls.assert_called_once()
    mock_sock.sendto.assert_called_once_with(b"READY=1", SOCK_PATH)
    mock_sock.close.assert_called_once()


def test_notify_watchdog_sends_watchdog_byte(monkeypatch):
    """notify_watchdog() envia b"WATCHDOG=1"."""
    monkeypatch.setenv("NOTIFY_SOCKET", SOCK_PATH)

    with patch.object(systemd_notify.socket, "AF_UNIX", 1, create=True), \
         patch.object(systemd_notify.socket, "socket") as mock_socket_cls:
        mock_sock = mock_socket_cls.return_value
        result = notify_watchdog()

    assert result is True
    mock_sock.sendto.assert_called_once_with(b"WATCHDOG=1", SOCK_PATH)


def test_notify_stopping_sends_stopping_byte(monkeypatch):
    """notify_stopping() envia b"STOPPING=1"."""
    monkeypatch.setenv("NOTIFY_SOCKET", SOCK_PATH)

    with patch.object(systemd_notify.socket, "AF_UNIX", 1, create=True), \
         patch.object(systemd_notify.socket, "socket") as mock_socket_cls:
        mock_sock = mock_socket_cls.return_value
        result = notify_stopping()

    assert result is True
    mock_sock.sendto.assert_called_once_with(b"STOPPING=1", SOCK_PATH)


def test_notify_returns_false_on_oserror(monkeypatch):
    """Si sendto lanza OSError, notify() retorna False sin propagar."""
    monkeypatch.setenv("NOTIFY_SOCKET", SOCK_PATH)

    with patch.object(systemd_notify.socket, "AF_UNIX", 1, create=True), \
         patch.object(systemd_notify.socket, "socket") as mock_socket_cls:
        mock_socket_cls.return_value.sendto.side_effect = OSError("socket roto")
        result = notify_ready()

    assert result is False
