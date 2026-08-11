"""Servicios de negocio del backend HMI.

Expone los servicios principales:
- StateManager: estado compartido thread-safe con broadcast WebSocket.
- GPIOService: abstraccion del hardware GPIO via gpiozero.
"""

from backend.app.services.state_manager import StateManager
from backend.app.services.gpio_service import GPIOService

__all__ = ["GPIOService", "StateManager"]
