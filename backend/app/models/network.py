"""Modelos Pydantic para la configuracion de red.

Define el estado actual de la red y las peticiones para cambiarla
(IP estatica o DHCP) via NetworkManager (nmcli).
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, Field, field_validator


class NetworkStatus(BaseModel):
    """Estado actual de la conexion de red activa.

    Attributes:
        interface: Nombre de la interfaz (ej. 'eth0').
        connection_name: Nombre de la conexion NetworkManager (ej. 'Wired connection 1').
        mode: Modo de direccionamiento ('dhcp' o 'static').
        ip_address: Direccion IP actual (None si no disponible).
        prefix: Prefijo CIDR de la mascara (ej. 24) (None si no disponible).
        gateway: Puerta de enlace por defecto (None si no disponible).
        dns: Servidor DNS principal (None si no configurado).
    """

    interface: Annotated[str, Field(description="Interfaz de red activa (eth0, wlan0...)")]
    connection_name: Annotated[str, Field(description="Nombre de la conexion NetworkManager")]
    mode: Annotated[Literal["dhcp", "static"], Field(description="Modo de direccionamiento")]
    ip_address: Annotated[str | None, Field(description="Direccion IP actual")]
    prefix: Annotated[int | None, Field(ge=0, le=32, description="Prefijo CIDR (mascara)")]
    gateway: Annotated[str | None, Field(description="Puerta de enlace")]
    dns: Annotated[str | None, Field(description="Servidor DNS principal")]


class StaticIpRequest(BaseModel):
    """Peticion para configurar una IP estatica.

    Attributes:
        ip_address: Direccion IPv4 a asignar (ej. '192.168.1.50').
        prefix: Prefijo CIDR de la mascara (ej. 24 -> 255.255.255.0).
        gateway: Puerta de enlace (ej. '192.168.1.1').
        dns: Servidor DNS (opcional; por defecto se usa el gateway).
    """

    ip_address: Annotated[str, Field(description="Direccion IPv4 (ej. 192.168.1.50)")]
    prefix: Annotated[int, Field(ge=1, le=32, description="Prefijo CIDR (ej. 24)")]
    gateway: Annotated[str, Field(description="Puerta de enlace (ej. 192.168.1.1)")]
    dns: Annotated[str | None, Field(default=None, description="DNS (opcional, por defecto gateway)")]

    @field_validator("ip_address", "gateway", "dns")
    @classmethod
    def _validate_ipv4(cls, value: str | None) -> str | None:
        """Valida que el valor sea una IPv4 valida (o None para dns)."""
        if value is None:
            return None
        import ipaddress

        try:
            ipaddress.IPv4Address(value)
        except ValueError as exc:
            raise ValueError(f"IPv4 invalida: {value}") from exc
        return value


class NetworkResult(BaseModel):
    """Resultado de una operacion de configuracion de red.

    Attributes:
        success: True si la operacion se aplico correctamente.
        message: Descripcion legible del resultado.
        status: Estado de red actualizado tras la operacion (None si fallo).
    """

    success: Annotated[bool, Field(description="True si se aplico correctamente")]
    message: Annotated[str, Field(description="Descripcion del resultado")]
    status: Annotated[NetworkStatus | None, Field(description="Estado tras la operacion")]
