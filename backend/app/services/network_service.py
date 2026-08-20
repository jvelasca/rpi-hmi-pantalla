"""NetworkService — Gestion de red via NetworkManager (nmcli).

Proporciona lectura del estado de red y aplicacion de configuracion
(IP estatica o DHCP) usando `nmcli` de NetworkManager, presente en
Raspberry Pi OS Bookworm.

Los cambios de IP se aplican re-activando la conexion. Como esto puede
cortar la conexion actual (HTTP/SSH), la re-activacion se lanza en un
proceso en segundo plano tras un breve delay, de modo que el endpoint
pueda devolver la respuesta antes de que la red caiga.

Uso:
    from backend.app.services.network_service import network_service

    status = network_service.get_status()
    result = network_service.apply_static("192.168.1.50", 24, "192.168.1.1", "192.168.1.1")
"""

from __future__ import annotations

import logging
import shutil
import subprocess
import threading
import time
from typing import Any, Literal

from backend.app.models.network import NetworkResult, NetworkStatus

logger = logging.getLogger(__name__)

__all__ = ["NetworkService", "network_service"]

_NMCLI = "nmcli"
_ACTIVATE_DELAY = 1.0  # segundos antes de re-activar la conexion


class NetworkService:
    """Servicio de gestion de red basado en nmcli."""

    @property
    def available(self) -> bool:
        """True si nmcli esta disponible en el sistema."""
        return shutil.which(_NMCLI) is not None

    # ── Ejecucion de comandos ──────────────────────────────────

    @staticmethod
    def _run(cmd: list[str], timeout: int = 10, sudo: bool = False) -> tuple[int, str, str]:
        """Ejecuta un comando y devuelve (exit_code, stdout, stderr)."""
        full = (["sudo"] if sudo else []) + cmd
        try:
            proc = subprocess.run(
                full,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            return proc.returncode, proc.stdout.strip(), proc.stderr.strip()
        except FileNotFoundError:
            return 127, "", "comando no encontrado"
        except subprocess.TimeoutExpired:
            return 124, "", "timeout"

    def _activate_async(self, connection_name: str) -> None:
        """Re-activa la conexion en segundo plano tras un breve delay.

        Se ejecuta en un hilo daemon para no bloquear al endpoint y para
        dar tiempo a que la respuesta HTTP se haya enviado.
        """

        def _do() -> None:
            time.sleep(_ACTIVATE_DELAY)
            logger.info("Re-activando conexion '%s'...", connection_name)
            code, out, err = self._run(
                [_NMCLI, "con", "up", connection_name], timeout=20, sudo=True
            )
            if code == 0:
                logger.info("Conexion '%s' re-activada", connection_name)
            else:
                logger.warning("No se pudo re-activar '%s': %s %s", connection_name, out, err)

        threading.Thread(target=_do, daemon=True, name="network-activate").start()

    # ── Descubrimiento de conexion activa ──────────────────────

    def _active_ethernet(self) -> tuple[str, str] | None:
        """Devuelve (connection_name, device) de la conexion ethernet activa."""
        code, out, _ = self._run([_NMCLI, "-t", "-f", "NAME,DEVICE,TYPE,STATE", "con", "show", "--active"])
        if code != 0:
            return None
        for line in out.splitlines():
            parts = line.split(":")
            if len(parts) >= 4 and parts[2] == "802-3-ethernet" and parts[3] == "activated":
                return parts[0], parts[1]
        return None

    # ── Lectura de estado ──────────────────────────────────────

    def get_status(self) -> NetworkStatus:
        """Obtiene el estado actual de la red.

        Returns:
            NetworkStatus con la informacion de la conexion activa.
            En ausencia de nmcli devuelve un estado 'unknown' con campos None.
        """
        if not self.available:
            return NetworkStatus(
                interface="unknown",
                connection_name="",
                mode="dhcp",
                ip_address=None,
                prefix=None,
                gateway=None,
                dns=None,
            )

        active = self._active_ethernet()
        if active is None:
            logger.warning("No se encontro conexion ethernet activa")
            return NetworkStatus(
                interface="",
                connection_name="",
                mode="dhcp",
                ip_address=None,
                prefix=None,
                gateway=None,
                dns=None,
            )

        name, device = active

        # Metodo (dhcp/static) desde la conexion
        method = "dhcp"
        code, out, _ = self._run([_NMCLI, "-t", "-f", "ipv4.method", "con", "show", name])
        if code == 0:
            for line in out.splitlines():
                if line.startswith("ipv4.method:"):
                    method = line.split(":", 1)[1].strip()
                    break

        # IP real, gateway y DNS desde el dispositivo activo
        ip_address: str | None = None
        prefix: int | None = None
        gateway: str | None = None
        dns: str | None = None

        code, out, _ = self._run([_NMCLI, "-t", "-f", "IP4.ADDRESS,IP4.GATEWAY,IP4.DNS", "device", "show", device])
        if code == 0:
            for line in out.splitlines():
                if line.startswith("IP4.ADDRESS[") and ":" in line:
                    addr = line.split(":", 1)[1].strip()
                    if "/" in addr:
                        ip_address, p = addr.split("/", 1)
                        try:
                            prefix = int(p)
                        except ValueError:
                            prefix = None
                    else:
                        ip_address = addr
                elif line.startswith("IP4.GATEWAY:") and ":" in line:
                    gateway = line.split(":", 1)[1].strip() or None
                elif line.startswith("IP4.DNS[") and ":" in line:
                    dns = line.split(":", 1)[1].strip() or None

        mode: Literal["dhcp", "static"] = "static" if method == "manual" else "dhcp"
        return NetworkStatus(
            interface=device,
            connection_name=name,
            mode=mode,
            ip_address=ip_address,
            prefix=prefix,
            gateway=gateway,
            dns=dns,
        )

    # ── Aplicacion de configuracion ────────────────────────────

    def apply_static(self, ip_address: str, prefix: int, gateway: str, dns: str | None) -> NetworkResult:
        """Configura una IP estatica y re-activa la conexion.

        Args:
            ip_address: Direccion IPv4.
            prefix: Prefijo CIDR (1-32).
            gateway: Puerta de enlace.
            dns: Servidor DNS (None usa el gateway).

        Returns:
            NetworkResult con el resultado de la operacion.
        """
        if not self.available:
            return NetworkResult(success=False, message="nmcli no disponible en este sistema", status=None)

        active = self._active_ethernet()
        if active is None:
            return NetworkResult(success=False, message="No se encontro conexion ethernet activa", status=None)

        name, _device = active
        dns_value = dns or gateway

        cmd = [
            _NMCLI, "con", "mod", name,
            "ipv4.method", "manual",
            "ipv4.addresses", f"{ip_address}/{prefix}",
            "ipv4.gateway", gateway,
            "ipv4.dns", dns_value,
        ]
        code, out, err = self._run(cmd, timeout=10, sudo=True)
        if code != 0:
            logger.error("nmcli con mod fallo: %s", err or out)
            return NetworkResult(
                success=False,
                message=f"No se pudo aplicar la IP estatica: {err or out}",
                status=self.get_status(),
            )

        logger.info("IP estatica configurada en '%s': %s/%d gw=%s", name, ip_address, prefix, gateway)
        self._activate_async(name)
        return NetworkResult(
            success=True,
            message=f"IP estatica {ip_address}/{prefix} aplicada. La conexion se reiniciara.",
            status=self.get_status(),
        )

    def apply_dhcp(self) -> NetworkResult:
        """Cambia la conexion a DHCP (automatico) y re-activa.

        Returns:
            NetworkResult con el resultado de la operacion.
        """
        if not self.available:
            return NetworkResult(success=False, message="nmcli no disponible en este sistema", status=None)

        active = self._active_ethernet()
        if active is None:
            return NetworkResult(success=False, message="No se encontro conexion ethernet activa", status=None)

        name, _device = active

        cmd = [
            _NMCLI, "con", "mod", name,
            "ipv4.method", "auto",
            "ipv4.addresses", "",
            "ipv4.gateway", "",
            "ipv4.dns", "",
        ]
        code, out, err = self._run(cmd, timeout=10, sudo=True)
        if code != 0:
            logger.error("nmcli con mod (dhcp) fallo: %s", err or out)
            return NetworkResult(
                success=False,
                message=f"No se pudo cambiar a DHCP: {err or out}",
                status=self.get_status(),
            )

        logger.info("DHCP configurado en '%s'", name)
        self._activate_async(name)
        return NetworkResult(
            success=True,
            message="Modo DHCP aplicado. La conexion se reiniciara.",
            status=self.get_status(),
        )


# ── Singleton ──────────────────────────────────────────────────

network_service = NetworkService()
"""Instancia unica global del NetworkService."""
