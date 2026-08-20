"""Servicios de negocio del backend HMI.

Expone los servicios principales:
- StateManager: estado compartido thread-safe con broadcast WebSocket.
- GPIOService: abstraccion del hardware GPIO via gpiozero.
- Persistence: capa de persistencia SQLite asincrona.
"""

from backend.app.services.gpio_service import GPIOService
from backend.app.services.persistence import Persistence
from backend.app.services.state_manager import StateManager

__all__ = ["GPIOService", "StateManager", "Persistence"]
