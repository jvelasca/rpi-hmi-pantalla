"""Endpoints REST para la gestion de red.

Permite leer el estado de red y aplicar cambios (IP estatica o DHCP)
sobre la conexion ethernet activa usando NetworkManager.

Endpoints:
    GET  /api/network        -> Estado de red actual
    POST /api/network/static -> Aplicar IP estatica
    POST /api/network/dhcp   -> Cambiar a DHCP
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from backend.app.models.network import NetworkResult, NetworkStatus, StaticIpRequest
from backend.app.services.network_service import network_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/network", tags=["Network"])


@router.get("", response_model=NetworkStatus)
async def get_network() -> NetworkStatus:
    """Estado actual de la red.

    Returns:
        NetworkStatus con interfaz, IP, modo (dhcp/static), gateway y DNS.
    """
    return network_service.get_status()


@router.post("/static", response_model=NetworkResult)
async def set_static_ip(request: StaticIpRequest) -> NetworkResult:
    """Aplica una configuracion de IP estatica.

    AVISO: al re-activar la conexion la sesion actual (web/SSH) se cortara
    temporalmente hasta que la nueva IP este activa.

    Returns:
        NetworkResult con el resultado.
    """
    result = network_service.apply_static(
        ip_address=request.ip_address,
        prefix=request.prefix,
        gateway=request.gateway,
        dns=request.dns,
    )
    if not result.success:
        raise HTTPException(status_code=400, detail=result.message)
    return result


@router.post("/dhcp", response_model=NetworkResult)
async def set_dhcp() -> NetworkResult:
    """Cambia la conexion a DHCP (IP automatica).

    AVISO: al re-activar la conexion la sesion actual (web/SSH) se cortara
    temporalmente hasta que el router asigne una nueva IP.

    Returns:
        NetworkResult con el resultado.
    """
    result = network_service.apply_dhcp()
    if not result.success:
        raise HTTPException(status_code=400, detail=result.message)
    return result
