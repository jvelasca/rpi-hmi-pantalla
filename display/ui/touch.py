"""Touch handler — Driver táctil ADS7846/XPT2046 via evdev.

Lee eventos raw del dispositivo táctil y aplica una transformación afín
para mapear coordenadas raw a coordenadas de pantalla.

La transformación afín se calcula mediante un asistente de calibración
(toca las 4 esquinas + centro) y se guarda en un archivo JSON. Si no hay
calibración guardada, la app arranca automáticamente el asistente.

El debounce corrige el jitter del panel resistivo: un toque físico genera
una única llamada a on_touch_down, no una ráfaga de eventos.
"""

from __future__ import annotations

import json
import logging
import os
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

# Umbrales de presión para detectar pulsación/liberación
PRESS_THRESHOLD = 100
RELEASE_THRESHOLD = 50

# Tiempo mínimo entre dos pulsaciones (segundos) — debounce
DEBOUNCE_SECONDS = 0.08


def _find_touch_device() -> str | None:
    """Encuentra el dispositivo táctil ADS7846/XPT2046 en /dev/input/."""
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


def _default_calibration_path() -> Path:
    """Ruta del archivo de calibración (config/touch_calibration.json)."""
    return Path(__file__).resolve().parents[2] / "config" / "touch_calibration.json"


def solve_affine(points: list[tuple[int, int, int, int]]) -> tuple[float, float, float, float, float, float]:
    """Resuelve una transformación afín por mínimos cuadrados.

    Args:
        points: lista de (raw_x, raw_y, screen_x, screen_y).

    Returns:
        (a, b, c, d, e, f) tal que:
            screen_x = a*raw_x + b*raw_y + c
            screen_y = d*raw_x + e*raw_y + f
    """
    n = float(len(points))
    if len(points) < 3:
        raise ValueError("Se necesitan al menos 3 puntos para calibrar")

    S_rx2 = sum(rx * rx for rx, ry, sx, sy in points)
    S_rxry = sum(rx * ry for rx, ry, sx, sy in points)
    S_rx = sum(rx for rx, ry, sx, sy in points)
    S_ry2 = sum(ry * ry for rx, ry, sx, sy in points)
    S_ry = sum(ry for rx, ry, sx, sy in points)
    S_sx = sum(sx for rx, ry, sx, sy in points)
    S_sy = sum(sy for rx, ry, sx, sy in points)
    S_rxsx = sum(rx * sx for rx, ry, sx, sy in points)
    S_rysx = sum(ry * sx for rx, ry, sx, sy in points)
    S_rxsy = sum(rx * sy for rx, ry, sx, sy in points)
    S_rysy = sum(ry * sy for rx, ry, sx, sy in points)

    mat = [
        [S_rx2, S_rxry, S_rx],
        [S_rxry, S_ry2, S_ry],
        [S_rx, S_ry, n],
    ]
    a, b, c = _solve3(mat, [S_rxsx, S_rysx, S_sx])
    d, e, f = _solve3(mat, [S_rxsy, S_rysy, S_sy])
    return a, b, c, d, e, f


def _solve3(mat: list[list[float]], rhs: list[float]) -> tuple[float, float, float]:
    """Resuelve un sistema lineal 3x3 por eliminación gaussiana con pivoteo."""
    M = [list(r) for r in mat]
    b = list(rhs)
    for col in range(3):
        piv = max(range(col, 3), key=lambda i: abs(M[i][col]))
        if abs(M[piv][col]) < 1e-12:
            raise ValueError("Sistema singular — puntos colineales")
        M[col], M[piv] = M[piv], M[col]
        b[col], b[piv] = b[piv], b[col]
        for i in range(col + 1, 3):
            factor = M[i][col] / M[col][col]
            for j in range(col, 3):
                M[i][j] -= factor * M[col][j]
            b[i] -= factor * b[col]
    x = [0.0, 0.0, 0.0]
    for i in range(2, -1, -1):
        s = b[i]
        for j in range(i + 1, 3):
            s -= M[i][j] * x[j]
        x[i] = s / M[i][i]
    return x[0], x[1], x[2]


class TouchHandler:
    """Lee eventos táctiles y aplica una transformación afín calibrada.

    Atributos:
        device_path: Ruta al dispositivo evdev.
        screen_width / screen_height: dimensiones de pantalla en píxeles.
        has_calibration: True si se cargó una calibración guardada.
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
        calibration_file: str | None = None,
    ) -> None:
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.touch_max_x = touch_max_x
        self.touch_max_y = touch_max_y
        self.invert_x = invert_x
        self.invert_y = invert_y
        self.calibration_file = calibration_file or str(_default_calibration_path())

        self.device_path: str | None = None
        self._fd: int | None = None

        # Estado actual del touch (coordenadas raw)
        self.x: int = 0
        self.y: int = 0
        self.pressure: int = 0
        self.touching: bool = False
        self._btn_touch: bool = False
        self._last_down_time: float = 0.0

        # Callbacks
        self.on_touch_down: callable | None = None   # (screen_x, screen_y)
        self.on_touch_up: callable | None = None     # (screen_x, screen_y)
        self.on_touch_move: callable | None = None   # (screen_x, screen_y)

        # Transformación afín: screen = A * raw + b
        # Por defecto: rotate=270 (X raw -> -Y, Y raw -> X)
        self.has_calibration = False
        self._a_xx = 0.0
        self._a_xy = self.screen_width / self.touch_max_y
        self._a_yx = -self.screen_height / self.touch_max_x
        self._a_yy = 0.0
        self._b_x = 0.0
        self._b_y = self.screen_height - 1

        self._load_calibration()
        self._init_device(device_path)

    # ── Inicialización ─────────────────────────────────────────

    def _init_device(self, device_path: str | None) -> None:
        """Abre el dispositivo táctil en modo no bloqueante."""
        path = device_path or _find_touch_device()
        if path is None:
            logger.warning("Dispositivo táctil no encontrado")
            return

        try:
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

    # ── Calibración ────────────────────────────────────────────

    def _load_calibration(self) -> None:
        """Carga la calibración guardada si existe."""
        path = Path(self.calibration_file)
        if not path.exists():
            logger.info("Sin calibración táctil guardada (se usará por defecto)")
            return
        try:
            data = json.loads(path.read_text())
            self._a_xx = float(data["a_xx"])
            self._a_xy = float(data["a_xy"])
            self._a_yx = float(data["a_yx"])
            self._a_yy = float(data["a_yy"])
            self._b_x = float(data["b_x"])
            self._b_y = float(data["b_y"])
            self.has_calibration = True
            logger.info("Calibración táctil cargada desde %s", path)
        except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
            logger.warning("No se pudo cargar calibración: %s", exc)

    def set_calibration_from_points(
        self, points: list[tuple[int, int, int, int]]
    ) -> tuple[float, float, float, float, float, float]:
        """Calcula y guarda la calibración a partir de puntos (raw, screen)."""
        coeffs = solve_affine(points)
        self._a_xx, self._a_xy, self._b_x, self._a_yx, self._a_yy, self._b_y = (
            coeffs[0], coeffs[1], coeffs[2], coeffs[3], coeffs[4], coeffs[5],
        )
        self.has_calibration = True

        path = Path(self.calibration_file)
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "a_xx": coeffs[0], "a_xy": coeffs[1], "b_x": coeffs[2],
            "a_yx": coeffs[3], "a_yy": coeffs[4], "b_y": coeffs[5],
        }
        path.write_text(json.dumps(data, indent=2))
        logger.info("Calibración táctil guardada en %s", path)
        return coeffs

    # ── Lectura de eventos ─────────────────────────────────────

    def poll(self) -> int:
        """Lee todos los eventos táctiles pendientes."""
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
        """Procesa un evento evdev con detección de borde (debounce).

        La decisión de pulsación/liberación se toma SOLO en SYN_REPORT,
        usando BTN_TOUCH y el nivel de presión. Esto garantiza una única
        llamada a on_touch_down por toque físico.
        """
        if ev_type == EV_ABS:
            if ev_code == ABS_X:
                self.x = ev_value
            elif ev_code == ABS_Y:
                self.y = ev_value
            elif ev_code == ABS_PRESSURE:
                self.pressure = ev_value
            return 0

        if ev_type == EV_KEY and ev_code == BTN_TOUCH:
            self._btn_touch = ev_value == 1
            return 0

        if ev_type == EV_SYN and ev_code == SYN_REPORT:
            pressed = self._btn_touch or self.pressure > PRESS_THRESHOLD

            if pressed and not self.touching:
                now = time.time()
                if now - self._last_down_time < DEBOUNCE_SECONDS:
                    return 0  # ignorar rebote
                self.touching = True
                self._last_down_time = now
                sx, sy = self.raw_to_screen(self.x, self.y)
                if self.on_touch_down:
                    self.on_touch_down(sx, sy)
                return 1

            if not pressed and self.touching:
                self.touching = False
                sx, sy = self.raw_to_screen(self.x, self.y)
                if self.on_touch_up:
                    self.on_touch_up(sx, sy)
                return 1

            if pressed and self.touching:
                sx, sy = self.raw_to_screen(self.x, self.y)
                if self.on_touch_move:
                    self.on_touch_move(sx, sy)
                return 1

        return 0

    # ── Mapeo de coordenadas ───────────────────────────────────

    def raw_to_screen(self, raw_x: int, raw_y: int) -> tuple[int, int]:
        """Aplica la transformación afín calibrada."""
        sx = self._a_xx * raw_x + self._a_xy * raw_y + self._b_x
        sy = self._a_yx * raw_x + self._a_yy * raw_y + self._b_y

        sx = max(0, min(self.screen_width - 1, int(round(sx))))
        sy = max(0, min(self.screen_height - 1, int(round(sy))))

        logger.debug(
            "raw=(%d,%d) -> screen=(%d,%d) [w=%d h=%d]",
            raw_x, raw_y, sx, sy, self.screen_width, self.screen_height,
        )
        return (sx, sy)

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
