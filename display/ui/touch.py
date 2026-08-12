"""Touch handler — Driver táctil ADS7846/XPT2046 via evdev.

Lee eventos raw del dispositivo táctil, aplica mapeo de coordenadas
(rotate=270 del overlay ads7846) y proporciona callbacks de alto nivel
(touch_down, touch_up, touch_move).
"""

from __future__ import annotations

import logging
import struct
import time
from pathlib import Path

logger = logging.getLogger("rpi_hmi.display.touch")

# ── Constantes evdev ──────────────────────────────────────────
EV_SYN = 0
EV_KEY = 1
EV_ABS = 3
SYN_REPORT = 0
ABS_X = 0
ABS_Y = 1
ABS_PRESSURE = 24
BTN_TOUCH = 330

# Rango típico del XPT2046
RAW_MAX = 4096


def _find_touch_device() -> str | None:
    """Encuentra el dispositivo táctil ADS7846/XPT2046 en /dev/input/.

    Busca por nombre de dispositivo en sysfs. Si no encuentra ninguno,
    devuelve None (sin fallback a event0).

    Returns:
        Ruta al dispositivo o None si no se encuentra.
    """
    candidates: list[str] = []
    for i in range(10):
        dev = f"/dev/input/event{i}"
        if Path(dev).exists():
            candidates.append(dev)

    for dev in candidates:
        name_path = f"/sys/class/input/{Path(dev).name}/device/name"
        try:
            with open(name_path) as f:
                name = f.read().strip().lower()
                if any(kw in name for kw in ("touch", "ads7846", "xpt", "ft5x", "gt9", "stmpe")):
                    return dev
        except OSError:
            pass

    logger.warning("No se encontro dispositivo tactil. Touch deshabilitado.")
    return None


class TouchHandler:
    """Lee eventos táctiles desde /dev/input/event* y convierte coordenadas.

    Maneja el mapeo de coordenadas para el overlay ads7846 con rotate=270,
    que es la configuración estándar para displays ILI9486 en Raspberry Pi.

    Atributos:
        device_path: Ruta al dispositivo evdev.
        screen_width: Ancho de la pantalla en píxeles.
        screen_height: Alto de la pantalla en píxeles.
        touch_max_x: Valor máximo del eje X raw (default 4096).
        touch_max_y: Valor máximo del eje Y raw (default 4096).
        invert_x: Invertir eje X tras el mapeo.
        invert_y: Invertir eje Y tras el mapeo.
    """

    def __init__(
        self,
        device_path: str | None = None,
        screen_width: int = 480,
        screen_height: int = 320,
        touch_max_x: int = RAW_MAX,
        touch_max_y: int = RAW_MAX,
        invert_x: bool = False,
        invert_y: bool = False,
    ) -> None:
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.touch_max_x = touch_max_x
        self.touch_max_y = touch_max_y
        self.invert_x = invert_x
        self.invert_y = invert_y

        self.device_path: str | None = None
        self._fd: int | None = None

        # Estado actual del touch
        self.x: int = 0
        self.y: int = 0
        self.pressure: int = 0
        self.touching: bool = False

        # Callbacks
        self.on_touch_down: callable | None = None   # (screen_x, screen_y)
        self.on_touch_up: callable | None = None     # (screen_x, screen_y)
        self.on_touch_move: callable | None = None   # (screen_x, screen_y)

        self._init_device(device_path)

    # ── Inicialización ─────────────────────────────────────────

    def _init_device(self, device_path: str | None) -> None:
        """Abre el dispositivo táctil en modo no bloqueante."""
        path = device_path or _find_touch_device()
        if path is None:
            logger.warning("Dispositivo táctil no encontrado")
            return

        try:
            # os.O_NONBLOCK es especifico de Linux
            flags = os.O_RDONLY
            if hasattr(os, "O_NONBLOCK"):
                flags |= os.O_NONBLOCK
            fd = os.open(path, flags)
            self._fd = fd
            self.device_path = path
            logger.info("Touch inicializado en %s", path)
        except OSError as exc:
            logger.warning("No se pudo abrir %s: %s", path, exc)

    @property
    def available(self) -> bool:
        return self._fd is not None

    # ── Lectura de eventos ─────────────────────────────────────

    def poll(self) -> int:
        """Lee todos los eventos táctiles pendientes.

        Returns:
            Número de eventos SYN_REPORT procesados.
        """
        if self._fd is None:
            return 0

        syn_count = 0
        try:
            while True:
                data = os.read(self._fd, 16)
                if len(data) < 16:
                    break
                _sec, _usec, ev_type, ev_code, ev_value = struct.unpack(
                    "<llHHi", data
                )
                syn_count += self._process_event(ev_type, ev_code, ev_value)
        except (BlockingIOError, OSError):
            pass
        return syn_count

    def _process_event(self, ev_type: int, ev_code: int, ev_value: int) -> int:
        """Procesa un evento evdev individual.

        Returns:
            1 si fue un SYN_REPORT procesado, 0 en otro caso.
        """
        if ev_type == EV_ABS:
            if ev_code == ABS_X:
                self.x = ev_value
            elif ev_code == ABS_Y:
                self.y = ev_value
            elif ev_code == ABS_PRESSURE:
                self.pressure = ev_value

        elif ev_type == EV_KEY and ev_code == BTN_TOUCH:
            if ev_value == 0 and self.touching:
                self.touching = False
                sx, sy = self.raw_to_screen(self.x, self.y)
                if self.on_touch_up:
                    self.on_touch_up(sx, sy)
                return 1
            elif ev_value == 1 and not self.touching:
                self.touching = True
                sx, sy = self.raw_to_screen(self.x, self.y)
                if self.on_touch_down:
                    self.on_touch_down(sx, sy)
                return 1

        elif ev_type == EV_SYN and ev_code == SYN_REPORT:
            if self.pressure > 100 and not self.touching:
                # Touch sin BTN_TOUCH (algunos drivers no emiten BTN_TOUCH)
                self.touching = True
                sx, sy = self.raw_to_screen(self.x, self.y)
                if self.on_touch_down:
                    self.on_touch_down(sx, sy)
                return 1
            elif self.pressure < 50 and self.touching:
                self.touching = False
                sx, sy = self.raw_to_screen(self.x, self.y)
                if self.on_touch_up:
                    self.on_touch_up(sx, sy)
                return 1
            elif self.touching:
                # Movimiento
                sx, sy = self.raw_to_screen(self.x, self.y)
                if self.on_touch_move:
                    self.on_touch_move(sx, sy)
                return 1

        return 0

    # ── Mapeo de coordenadas ───────────────────────────────────

    def raw_to_screen(self, raw_x: int, raw_y: int) -> tuple[int, int]:
        """Convierte coordenadas raw del touch a coordenadas de pantalla.

        El overlay ads7846 está configurado con rotate=270, swapxy=0.
        Mapeo para rotate=270:
            screen_y = height - 1 - int(raw_x * height / touch_max_x)
            screen_x = int(raw_y * width / touch_max_y)
        """
        w, h = self.screen_width, self.screen_height

        # rotate=270: X raw → Y invertido, Y raw → X directo
        screen_y = h - 1 - int(raw_x * h / self.touch_max_x)
        screen_x = int(raw_y * w / self.touch_max_y)

        if self.invert_x:
            screen_x = w - 1 - screen_x
        if self.invert_y:
            screen_y = h - 1 - screen_y

        return (screen_x, screen_y)

    # ── Limpieza ───────────────────────────────────────────────

    def close(self) -> None:
        """Cierra el dispositivo táctil."""
        if self._fd is not None:
            try:
                os.close(self._fd)
            except OSError:
                pass
            self._fd = None
            logger.debug("Touch cerrado")


# Import os at module level (needed for os.open/os.close)
import os  # noqa: E402
