"""StateManager — Estado compartido thread-safe del sistema.

Singleton que centraliza el estado de LED, boton y display,
y emite broadcasts WebSocket a todos los clientes suscritos.

Uso:
    from backend.app.services.state_manager import state_manager

    # Leer estado
    status = state_manager.get_status()

    # Modificar estado (con broadcast automatico)
    state_manager.toggle_led()

    # Suscribir cliente WebSocket
    await state_manager.subscribe(websocket, topics=["led", "button"])

Thread-safety: todos los metodos publicos usan `threading.Lock`
para garantizar acceso consistente desde multiples hilos y corutinas.
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from typing import Any

from backend.app.models.events import ServerMessage, SubscriptionTopic
from backend.app.models.hmi import ButtonState, DisplayInfo, LedState, SystemStatus

logger = logging.getLogger(__name__)

# Re-export para comodidad
__all__ = ["StateManager", "state_manager"]


class StateManager:
    """Gestiona el estado del sistema con broadcast WebSocket automatico.

    Thread-safe. Disenado como singleton (instancia unica `state_manager`).
    """

    def __init__(self) -> None:
        self._lock: threading.Lock = threading.Lock()
        self._start_time: float = time.monotonic()
        # Cargar pin desde devices.yaml (fuente unica de verdad)
        pin = self._load_led_pin()
        self._led_state: LedState = LedState(state=False, label="APAGADO", gpio_pin=pin)
        self._button_state: ButtonState = ButtonState(pressed=False, press_count=0)
        self._display_info: DisplayInfo | None = None
        self._subscribers: dict[str, set[Any]] = {}  # topic -> set(WebSocket)
        self._updater_callback: Any | None = None  # Callback para actualizar GPIO

    @staticmethod
    def _load_led_pin() -> int:
        """Carga el pin del LED desde devices.yaml.

        Busca el primer dispositivo con driver=gpio y mode=output
        en backend/config/devices.yaml.

        Returns:
            Numero de pin BCM, o 0 como fallback si no se encuentra.
        """
        try:
            from backend.app.services.gpio_service import load_devices

            devices = load_devices("backend/config/devices.yaml")
            for dev_id, dev in devices.items():
                if dev.config.get("driver") == "gpio" and dev.config.get("mode") == "output":
                    pin = int(dev.config.get("pin", 0))
                    logger.info("Pin LED cargado desde devices.yaml: %s -> GPIO %d", dev_id, pin)
                    return pin
            logger.warning("No se encontro dispositivo GPIO output en devices.yaml")
        except Exception:
            logger.warning("No se pudo cargar devices.yaml, usando pin 0 como fallback")
        return 0

    # ── Propiedades thread-safe ────────────────────────────────

    @property
    def led(self) -> LedState:
        """Estado actual del LED (thread-safe)."""
        with self._lock:
            return self._led_state.model_copy(deep=True)

    @property
    def button(self) -> ButtonState:
        """Estado actual del boton (thread-safe)."""
        with self._lock:
            return self._button_state.model_copy(deep=True)

    @property
    def display(self) -> DisplayInfo | None:
        """Info del display fisico (thread-safe)."""
        with self._lock:
            return self._display_info.model_copy(deep=True) if self._display_info else None

    # ── Acciones de estado ─────────────────────────────────────

    def set_led(self, state: bool) -> LedState:
        """Establece el estado del LED y notifica.

        Args:
            state: True para encender, False para apagar.

        Returns:
            Nuevo LedState.
        """
        label = "ENCENDIDO" if state else "APAGADO"
        with self._lock:
            self._led_state = LedState(state=state, label=label, gpio_pin=self._led_state.gpio_pin)

        # Notificar a la HAL para actualizar GPIO fisico
        if self._updater_callback:
            try:
                self._updater_callback("led", self._led_state)
            except Exception:
                logger.exception("Error en callback GPIO para LED")

        # Broadcast async
        msg = ServerMessage(type="led_changed", data=self._led_state.model_dump())
        self._schedule_broadcast(msg)
        logger.info("LED -> %s", label)
        return self._led_state

    def toggle_led(self) -> LedState:
        """Alterna el estado del LED.

        Returns:
            Nuevo LedState tras el toggle.
        """
        return self.set_led(not self.led.state)

    def press_button(self) -> ButtonState:
        """Registra una pulsacion del boton.

        Returns:
            ButtonState actualizado.
        """
        with self._lock:
            self._button_state = ButtonState(
                pressed=True,
                press_count=self._button_state.press_count + 1,
            )
        msg = ServerMessage(type="button_pressed", data=self._button_state.model_dump())
        self._schedule_broadcast(msg)
        logger.info("Boton presionado (count=%d)", self._button_state.press_count)
        return self._button_state

    def release_button(self) -> ButtonState:
        """Libera el boton.

        Returns:
            ButtonState actualizado.
        """
        with self._lock:
            self._button_state = ButtonState(
                pressed=False,
                press_count=self._button_state.press_count,
            )
        msg = ServerMessage(type="button_released", data=self._button_state.model_dump())
        self._schedule_broadcast(msg)
        logger.info("Boton liberado")
        return self._button_state

    def set_display(self, connected: bool, resolution: str = "480x320", driver: str = "ili9486") -> None:
        """Actualiza la informacion del display fisico.

        Args:
            connected: True si el display esta funcional.
            resolution: Resolucion WxH.
            driver: Nombre del driver kernel.
        """
        with self._lock:
            self._display_info = DisplayInfo(
                connected=connected,
                resolution=resolution,
                driver=driver,
            )
        msg = ServerMessage(type="display_changed", data=self._display_info.model_dump())
        self._schedule_broadcast(msg)
        logger.info("Display: connected=%s, %s, %s", connected, resolution, driver)

    # ── Consulta ───────────────────────────────────────────────

    def get_status(self) -> SystemStatus:
        """Obtiene el estado completo del sistema.

        Returns:
            SystemStatus con todos los subsistemas.
        """
        with self._lock:
            # Clientes unicos (set comprehension sobre todos los topics)
            unique_clients = {ws for subs in self._subscribers.values() for ws in subs}
            uptime = time.monotonic() - self._start_time
            return SystemStatus.from_manager(
                led=self._led_state,
                button=self._button_state,
                display=self._display_info,
                ws_count=len(unique_clients),
                uptime_seconds=uptime,
            )

    # ── Suscripciones WebSocket ────────────────────────────────

    async def subscribe(
        self, websocket: Any, topics: list[SubscriptionTopic] | None = None
    ) -> None:
        """Suscribe un cliente WebSocket a topicos.

        Args:
            websocket: Conexion WebSocket (starlette/fastapi).
            topics: Lista de topicos. None = todos.
        """
        if topics is None:
            topics = list(SubscriptionTopic)

        with self._lock:
            for topic in topics:
                self._subscribers.setdefault(topic.value, set()).add(websocket)

        # Enviar estado actual inmediatamente
        status = self.get_status()
        await websocket.send_json(
            ServerMessage(type="status_update", data=status.model_dump()).model_dump()
        )
        logger.debug("Cliente suscrito a %s", [t.value for t in topics])

    def unsubscribe(self, websocket: Any) -> None:
        """Elimina un cliente de todas las suscripciones.

        Args:
            websocket: Conexion WebSocket a eliminar.
        """
        with self._lock:
            for subscribers in self._subscribers.values():
                subscribers.discard(websocket)

    # ── Callback hardware ──────────────────────────────────────

    def set_updater(self, callback: Any) -> None:
        """Registra un callback llamado cuando cambia el estado del LED.

        Args:
            callback: Funcion con firma callback(device: str, state: LedState).
        """
        self._updater_callback = callback

    # ── Interno ────────────────────────────────────────────────

    def _schedule_broadcast(self, message: ServerMessage) -> None:
        """Programa un broadcast de forma segura en cualquier contexto.

        En contexto async: usa asyncio.create_task.
        En contexto sincrono: ignora (no hay clientes WS en tests unitarios).
        """
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self._broadcast(message))
        except RuntimeError:
            # No hay event loop (ej. tests sincronos) — ignorar
            logger.debug("Broadcast omitido (sin event loop): %s", message.type)

    async def _broadcast(self, message: ServerMessage) -> None:
        """Envia un mensaje a todos los suscriptores del topico correspondiente.

        Args:
            message: ServerMessage a enviar.
        """
        topic = message.type.split("_")[0]  # "led_changed" -> "led"
        payload = message.model_dump()

        subscribers: set[Any] = set()
        with self._lock:
            # Suscriptores especificos del topico + suscriptores de "system"
            for t in (topic, SubscriptionTopic.SYSTEM.value):
                if t in self._subscribers:
                    subscribers.update(self._subscribers[t])

        dead: list[Any] = []
        for ws in subscribers:
            try:
                await ws.send_json(payload)
            except Exception:
                dead.append(ws)

        # Limpiar conexiones muertas
        if dead:
            with self._lock:
                for s in self._subscribers.values():
                    for d in dead:
                        s.discard(d)


# ── Singleton ──────────────────────────────────────────────────

state_manager = StateManager()
"""Instancia unica global del StateManager."""
