"""Modelos Pydantic del sistema HMI.

Todos los modelos usan Pydantic v2 con validacion estricta (`strict=True`)
y estan disenados para ser serializables a JSON sin perdida de informacion.

Los tipos equivalentes en TypeScript se definen en `frontend/src/types/api.ts`
y deben mantenerse sincronizados manualmente (o via generacion automatica en CI).
"""

from backend.app.models.hmi import (
    ButtonState,
    DisplayCommand,
    DisplayInfo,
    DisplaySettings,
    LedState,
    SystemStatus,
)
from backend.app.models.events import (
    ClientMessage,
    ErrorDetail,
    ServerMessage,
    SubscriptionTopic,
)
from backend.app.models.device import (
    DeviceConfig,
    DeviceType,
    PinMapping,
)
from backend.app.models.network import (
    NetworkResult,
    NetworkStatus,
    StaticIpRequest,
)

__all__ = [
    "ButtonState",
    "ClientMessage",
    "DeviceConfig",
    "DeviceType",
    "DisplayCommand",
    "DisplayInfo",
    "DisplaySettings",
    "ErrorDetail",
    "LedState",
    "NetworkResult",
    "NetworkStatus",
    "PinMapping",
    "ServerMessage",
    "StaticIpRequest",
    "SubscriptionTopic",
    "SystemStatus",
]
