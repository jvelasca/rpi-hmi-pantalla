"""WebSocketHub — Suscripciones por topic y broadcast serializado.

Encapsula las responsabilidades de mensajeria WebSocket que antes vivian
dentro de `StateManager`:

- `_subscribers`: registro de clientes por topico (``topic -> set(WebSocket)``).
- `_sequence`: contador monotonicamente creciente para ordenar mensajes.
- `_broadcast_queues` + `_broadcast_workers`: entrega FIFO por topico.

`StateManager` DELEGA en esta clase, de modo que el estado de negocio (LED,
boton, display) queda desacoplado del transporte WebSocket.

Thread-safety: las operaciones sobre `_subscribers` usan el ``threading.Lock``
compartido que inyecta `StateManager` (o uno propio por defecto), garantizando
acceso consistente desde multiples hilos/corutinas.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from typing import Any

from backend.app.models.events import ServerMessage, SubscriptionTopic

logger = logging.getLogger(__name__)

__all__ = ["WebSocketHub"]


class WebSocketHub:
    """Registro de suscriptores y broadcast WebSocket serializado por topico."""

    def __init__(self, lock: threading.Lock | None = None) -> None:
        self._lock: threading.Lock = lock or threading.Lock()
        self._sequence: int = 0  # Contador de eventos para ordenamiento WS
        self._subscribers: dict[str, set[Any]] = {}  # topic -> set(WebSocket)
        self._broadcast_queues: dict[str, asyncio.Queue[Any]] = {}  # topic -> queue
        self._broadcast_workers: dict[str, asyncio.Task[Any]] = {}  # topic -> worker task

    # ── Suscripciones ─────────────────────────────────────────

    @property
    def subscribers(self) -> dict[str, set[Any]]:
        """Mapa de suscriptores por topico (solo lectura)."""
        return self._subscribers

    @property
    def sequence(self) -> int:
        """Ultimo numero de secuencia emitido."""
        return self._sequence

    def next_sequence(self) -> int:
        """Incrementa y devuelve el contador de secuencia.

        El llamador (StateManager) debe invocarlo mientras mantiene el lock
        compartido para evitar carreras read-modify-write entre hilos.
        """
        self._sequence += 1
        return self._sequence

    def subscribe(self, websocket: Any, topics: list[SubscriptionTopic]) -> None:
        """Registra un cliente en los topicos indicados.

        Args:
            websocket: Conexion WebSocket (starlette/fastapi).
            topics: Lista de topicos (enums SubscriptionTopic).
        """
        with self._lock:
            for topic in topics:
                self._subscribers.setdefault(topic.value, set()).add(websocket)

    def unsubscribe(self, websocket: Any) -> None:
        """Elimina un cliente de todas las suscripciones."""
        with self._lock:
            for subscribers in self._subscribers.values():
                subscribers.discard(websocket)

    # ── Broadcast ─────────────────────────────────────────────

    def schedule_broadcast(self, message: ServerMessage) -> None:
        """Programa un broadcast serializado por topico.

        Usa una cola por topico para garantizar que los mensajes se entregan
        en orden de sequence a cada cliente.
        """
        try:
            loop = asyncio.get_running_loop()
            topic = message.type.split("_")[0]  # "led_changed" -> "led"

            # Lazy-init queue and worker for this topic
            if topic not in self._broadcast_queues:
                self._broadcast_queues[topic] = asyncio.Queue()
                self._broadcast_workers[topic] = loop.create_task(
                    self._broadcast_worker(topic)
                )

            # Put message in the queue (non-blocking)
            self._broadcast_queues[topic].put_nowait(message)
        except RuntimeError:
            logger.debug("Broadcast omitido (sin event loop): %s", message.type)

    async def _broadcast_worker(self, topic: str) -> None:
        """Worker que serializa broadcasts para un topico.

        Garantiza que los mensajes se envian en orden FIFO
        a todos los suscriptores del topico.
        """
        queue = self._broadcast_queues.get(topic)
        if not queue:
            return

        while True:
            try:
                message = await queue.get()
                await self.broadcast(message)
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Error en broadcast worker para %s", topic)

    async def broadcast(self, message: ServerMessage) -> None:
        """Envia un mensaje a todos los suscriptores del topico correspondiente.

        Args:
            message: ServerMessage a enviar.
        """
        topic = message.type.split("_")[0]  # "led_changed" -> "led"
        payload = message.model_dump(mode="json")

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
