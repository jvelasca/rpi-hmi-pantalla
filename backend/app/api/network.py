"""Endpoints REST para la gestion de red.

Permite leer el estado de red y aplicar cambios (IP estatica o DHCP)
sobre la conexion ethernet activa usando NetworkManager.

Endpoints:
    GET  /api/network        -> Estado de red actual (publico, solo lectura)
    POST /api/network/static -> Aplicar IP estatica (protegido en SECURITY_MODE=protected)
    POST /api/network/dhcp   -> Cambiar a DHCP (protegido en SECURITY_MODE=protected)

Seguridad: ``GET`` es publico porque solo lee estado. Los ``POST`` mutan la
configuracion de red y exigen el header ``X-API-Key`` cuando
``SECURITY_MODE=protected`` (via ``require_admin_api_key``).
"""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException

from backend.app.api.deps import require_admin_api_key
from backend.app.models.network import NetworkResult, NetworkStatus, StaticIpRequest
from backend.app.services.network_service import network_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/network", tags=["Network"])


@router.get("", response_model=NetworkStatus)
async def get_network() -> NetworkStatus:
    """Estado actual de la red (publico, solo lectura).

    Returns:
        NetworkStatus con interfaz, IP, modo (dhcp/static), gateway y DNS.
    """
    # get_status() es sincrono (subprocess.run); se ejecuta en un thread
    # para no bloquear el event loop de FastAPI.
    return await asyncio.to_thread(network_service.get_status)


@router.post("/static", response_model=NetworkResult, dependencies=[Depends(require_admin_api_key)])
async def set_static_ip(request: StaticIpRequest) -> NetworkResult:
    """Aplica una configuracion de IP estatica.

    Requiere autenticacion (header X-API-Key) cuando SECURITY_MODE=protected.

    AVISO: al re-activar la conexion la sesion actual (web/SSH) se cortara
    temporalmente hasta que la nueva IP este activa.

    Returns:
        NetworkResult con el resultado.
    """
    result = await asyncio.to_thread(
        network_service.apply_static,
        ip_address=request.ip_address,
        prefix=request.prefix,
        gateway=request.gateway,
        dns=request.dns,
    )
    if not result.success:
        raise HTTPException(status_code=400, detail=result.message)
    return result


@router.post("/dhcp", response_model=NetworkResult, dependencies=[Depends(require_admin_api_key)])
async def set_dhcp() -> NetworkResult:
    """Cambia la conexion a DHCP (IP automatica).

    Requiere autenticacion (header X-API-Key) cuando SECURITY_MODE=protected.

    AVISO: al re-activar la conexion la sesion actual (web/SSH) se cortara
    temporalmente hasta que el router asigne una nueva IP.

    Returns:
        NetworkResult con el resultado.
    """
    result = await asyncio.to_thread(network_service.apply_dhcp)
    if not result.success:
        raise HTTPException(status_code=400, detail=result.message)
    return result
