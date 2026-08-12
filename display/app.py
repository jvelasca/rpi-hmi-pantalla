"""Display App — Pygame DRM/KMS HMI para Raspberry Pi ILI9486 3.5".

Entry point de la aplicacion de display fisico. Renderiza una interfaz
tactil con indicador LED, boton virtual y contador de pulsaciones.

Se comunica con el backend FastAPI (localhost:8000) via REST para comandos
y WebSocket para actualizaciones en tiempo real.

Uso:
    PYTHONPATH=/home/pi/rpi_hmi python3 display/app.py
    PYTHONPATH=/home/pi/rpi_hmi python3 display/app.py --api-url http://192.168.88.211:8000
    PYTHONPATH=/home/pi/rpi_hmi python3 display/app.py --mock  # modo desarrollo

Args:
    --api-url       URL base de la API REST (default: http://localhost:8000)
    --touch-device  Dispositivo táctil (default: auto-detect)
    --mock          Forzar modo mock (ventana en PC, sin DRM)
    --no-touch      Desactivar soporte táctil
    --fps           FPS objetivo (default: 20)
    --debug         Activar logging DEBUG
"""

from __future__ import annotations

import argparse
import json
import logging
import platform
import signal
import sys
import threading
import time

import requests

# ── Pygame import (puede fallar en PC sin pygame instalado) ──
try:
    import pygame  # noqa: E402
except ImportError as exc:
    _msg = (
        "\n"
        "=" * 55 + "\n"
        " ERROR: pygame no esta instalado\n"
        "\n"
        " Para desarrollo en PC, instala pygame con:\n"
        "   pip install pygame\n"
        "\n"
        " Despues ejecuta con --mock:\n"
        "   python display/app.py --mock\n"
        + "=" * 55 + "\n"
    )
    sys.exit(_msg)

from display.ui.screen import Screen  # noqa: E402
from display.ui.theme import (  # noqa: E402
    BASE_HEIGHT,
    BASE_WIDTH,
    BTN_PANEL_W,
    FOOTER_HEIGHT,
    HEADER_HEIGHT,
    LED_PANEL_W,
    LED_PANEL_X,
    MARGIN,
)
from display.ui.touch import TouchHandler  # noqa: E402
from display.ui.widgets import ButtonWidget, HeaderWidget, LedIndicator, StatusBar  # noqa: E402

logger = logging.getLogger("rpi_hmi.display")


# ═══════════════════════════════════════════════════════════════
# DisplayApp — Orquestador principal
# ═══════════════════════════════════════════════════════════════


class DisplayApp:
    """Aplicacion de display fisico con Pygame + DRM/KMS.

    Orquesta la pantalla, touch, widgets, y comunicacion con el backend.
    """

    def __init__(
        self,
        api_url: str = "http://localhost:8000",
        touch_device: str | None = None,
        mock: bool = False,
        no_touch: bool = False,
        fps: int = 20,
    ) -> None:
        self.api_url = api_url.rstrip("/")
        self.fps = fps
        self.running = False

        # Estado local (cache del backend)
        self.led_on: bool = False
        self.led_label: str = "APAGADO"
        self.press_count: int = 0
        self.backend_connected: bool = False
        self.ws_connected: bool = False
        self._last_sync: float = 0.0
        self._sync_interval: float = 3.0  # Solo como fallback cuando WS cae

        # Screen
        self.screen = Screen(auto_detect=not mock, mock=mock)

        # Touch
        self.touch: TouchHandler | None = None
        if not no_touch:
            self.touch = TouchHandler(
                device_path=touch_device,
                screen_width=BASE_WIDTH,
                screen_height=BASE_HEIGHT,
            )
            if self.touch.available:
                self.touch.on_touch_down = self._handle_touch_down
                self.touch.on_touch_up = self._handle_touch_up
                self.touch.on_touch_move = self._handle_touch_move
                logger.info("Touch handler conectado en %s", self.touch.device_path)
            elif mock:
                logger.info("Modo mock: usando mouse como touch")
            else:
                logger.warning("Touch no disponible")

        # Widgets
        self._create_widgets()

        # WebSocket background thread
        self._ws_thread: threading.Thread | None = None
        self._ws_lock = threading.Lock()
        self._ws_dirty: bool = False  # WS thread signals new data available

        # Button press feedback (non-blocking)
        self._button_press_frame: int = -1
        self._button_press_duration: int = 2  # frames

    # ── Layout ──────────────────────────────────────────────────

    def _create_widgets(self) -> None:
        """Crea los widgets con layout responsive para 480x320."""
        w, h = self.screen.width, self.screen.height

        # Escalar proporcionalmente respecto a 480x320
        sx = w / BASE_WIDTH
        sy = h / BASE_HEIGHT

        header_h = int(HEADER_HEIGHT * sy)
        footer_h = int(FOOTER_HEIGHT * sy)
        margin = int(MARGIN * sy)

        # Header
        self.header = HeaderWidget(0, 0, w, header_h)

        # Content area
        content_y = header_h + margin
        content_h = h - header_h - footer_h - margin * 2

        # Panel LED (izquierda)
        led_x = int(LED_PANEL_X * sx)
        led_w = int(LED_PANEL_W * sx)
        self.led = LedIndicator(led_x, content_y, led_w, content_h)

        # Panel Botón (derecha)
        btn_w = int(BTN_PANEL_W * sx)
        btn_x = w - btn_w - int(margin * sx)
        self.button = ButtonWidget(btn_x, content_y, btn_w, content_h)

        # Footer
        self.status_bar = StatusBar(0, h - footer_h, w, footer_h)

        # Conectar callbacks
        self.led.set_on_toggle(self._on_toggle_led)
        self.button.set_on_press(self._on_press_button)

        # Lista de widgets interactivos (orden de hit-test)
        self._interactive_widgets = [self.button, self.led]

        # Lista de todos los widgets a dibujar
        self._all_widgets = [self.header, self.led, self.button, self.status_bar]

    # ── Callbacks de widgets ────────────────────────────────────

    def _on_toggle_led(self) -> None:
        """Callback: el usuario tocó el botón toggle del LED."""
        logger.debug("Toggle LED solicitado")
        self._api_post("/api/led/toggle")
        # Sync inmediato para reflejar el cambio
        self._sync_state()

    def _on_press_button(self) -> None:
        """Callback: el usuario tocó el botón principal."""
        logger.debug("Button press solicitado")
        self.button.pressed = True
        self._button_press_frame = 0

        self._api_post("/api/button/press")
        self._sync_state()

    # ── Comunicacion con backend ────────────────────────────────

    def _api_get(self, endpoint: str) -> dict | None:
        """GET sincrono al backend REST."""
        try:
            resp = requests.get(f"{self.api_url}{endpoint}", timeout=2)
            resp.raise_for_status()
            self.backend_connected = True
            return resp.json()
        except requests.RequestException:
            self.backend_connected = False
            return None

    def _api_post(self, endpoint: str) -> dict | None:
        """POST sincrono al backend REST."""
        try:
            resp = requests.post(f"{self.api_url}{endpoint}", timeout=2)
            resp.raise_for_status()
            self.backend_connected = True
            return resp.json()
        except requests.RequestException:
            self.backend_connected = False
            return None

    def _sync_state(self) -> None:
        """Sincroniza el estado local con el backend via REST."""
        data = self._api_get("/api/status")
        if data is None:
            return
        led_data = data.get("led", {})
        btn_data = data.get("button", {})

        self.led_on = led_data.get("state", self.led_on)
        self.led_label = led_data.get("label", "APAGADO")
        self.press_count = btn_data.get("press_count", self.press_count)
        self.ws_connected = data.get("websocket_clients", 0) > 0

        # Actualizar widgets
        self.led.on = self.led_on
        self.led.label = self.led_label
        self.button.press_count = self.press_count

    # ── WebSocket (background thread) ───────────────────────────

    def _start_ws_thread(self) -> None:
        """Inicia el hilo de WebSocket para actualizaciones en tiempo real."""
        self._ws_thread = threading.Thread(
            target=self._ws_loop,
            daemon=True,
            name="display-ws",
        )
        self._ws_thread.start()
        logger.info("WebSocket thread iniciado")

    def _ws_loop(self) -> None:
        """Bucle del hilo WebSocket."""
        try:
            from websocket import WebSocketApp  # type: ignore[import-untyped]
        except ImportError:
            logger.warning("websocket-client no instalado. Usando solo REST.")
            return

        ws_url = self.api_url.replace("http://", "ws://") + "/ws"

        def on_open(ws: WebSocketApp) -> None:
            logger.info("WebSocket conectado a %s", ws_url)
            with self._ws_lock:
                self.ws_connected = True
            # Suscribirse a topicos
            ws.send(json.dumps({"type": "subscribe", "topics": ["led", "button"], "version": "1.0"}))

        def on_message(ws: WebSocketApp, message: str) -> None:
            try:
                msg = json.loads(message)
            except json.JSONDecodeError:
                return
            msg_type = msg.get("type", "")
            data = msg.get("data", {})

            with self._ws_lock:
                if msg_type == "led_changed":
                    self.led_on = data.get("state", self.led_on)
                    self.led_label = data.get("label", self.led_label)
                elif msg_type == "button_pressed":
                    self.press_count = data.get("press_count", self.press_count)
                elif msg_type == "status_update":
                    led_d = data.get("led", {})
                    btn_d = data.get("button", {})
                    self.led_on = led_d.get("state", self.led_on)
                    self.led_label = led_d.get("label", self.led_label)
                    self.press_count = btn_d.get("press_count", self.press_count)
                self._ws_dirty = True

        def on_error(ws: WebSocketApp, error: Exception) -> None:
            logger.debug("WS error: %s", error)

        def on_close(ws: WebSocketApp, close_status_code: int, close_msg: str) -> None:
            logger.info("WebSocket desconectado (code=%s)", close_status_code)
            with self._ws_lock:
                self.ws_connected = False

        # Bucle de reconexión
        while self.running:
            try:
                ws = WebSocketApp(
                    ws_url,
                    on_open=on_open,
                    on_message=on_message,
                    on_error=on_error,
                    on_close=on_close,
                )
                ws.run_forever(ping_interval=15, ping_timeout=5)
            except Exception as exc:
                logger.debug("WS exception: %s", exc)
            if self.running:
                time.sleep(2)  # Esperar antes de reconectar

    # ── Renderizado ─────────────────────────────────────────────

    def _render(self) -> None:
        """Renderiza todos los widgets en la pantalla."""
        surface = self.screen.get_surface()
        self.screen.clear()
        for widget in self._all_widgets:
            widget.draw(surface)

    # ── Bucle principal ─────────────────────────────────────────

    def run(self) -> int:
        """Ejecuta el bucle principal de la aplicacion.

        Returns:
            Codigo de salida (0 = ok).
        """
        if not self.screen.init():
            logger.error("No se pudo inicializar la pantalla")
            return 1

        # Actualizar tamanos de touch con la resolucion real
        if self.touch:
            self.touch.screen_width = self.screen.width
            self.touch.screen_height = self.screen.height

        # Marcar como running ANTES de iniciar el thread WebSocket,
        # para que while self.running en _ws_loop no termine inmediatamente.
        self.running = True

        # Iniciar WebSocket en background
        self._start_ws_thread()

        # Sincronizar estado inicial
        self._sync_state()
        self._last_sync = time.time()

        # Primer render
        self._render()
        self.screen.flip()
        logger.info(
            "Display app iniciada — %dx%d, driver=%s, fps=%d",
            self.screen.width,
            self.screen.height,
            self.screen.driver,
            self.fps,
        )
        logger.info("  API: %s", self.api_url)
        logger.info("  Touch: %s", self.touch.device_path if self.touch and self.touch.available else "no")
        logger.info("  ESC para salir")

        frame_count = 0

        while self.running:
            self.screen.tick(self.fps)
            dirty = False

            # ── Eventos Pygame (teclado, quit) ──
            for event in pygame.event.get():
                if self.screen.handle_quit(event):
                    self.running = False
                    break
                # En modo mock, clic del mouse simula touch
                if self.screen.mock and event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    self._dispatch_touch(event.pos[0], event.pos[1])
                    dirty = True

            if not self.running:
                break

            # ── Eventos touch (evdev) ──
            if self.touch and self.touch.available:
                self.touch.poll()

            # ── Aplicar estado recibido via WebSocket ──
            if self._apply_ws_state():
                dirty = True

            # ── Liberar boton tras feedback visual ──
            if self._button_press_frame >= 0:
                self._button_press_frame += 1
                if self._button_press_frame >= self._button_press_duration:
                    self.button.pressed = False
                    self._button_press_frame = -1
                    dirty = True

            # ── Sincronizacion periodica con backend (solo si WS no conectado) ──
            now = time.time()
            if now - self._last_sync > self._sync_interval:
                with self._ws_lock:
                    ws_ok = self.ws_connected
                if not ws_ok:
                    old_led = self.led_on
                    old_count = self.press_count
                    self._sync_state()
                    if old_led != self.led_on or old_count != self.press_count:
                        dirty = True
                self._last_sync = now

            # ── Actualizar status bar ──
            self.status_bar.time_str = time.strftime("%H:%M:%S")
            self.status_bar.backend_connected = self.backend_connected
            with self._ws_lock:
                self.status_bar.ws_connected = self.ws_connected
            self.status_bar.fps = self.screen.get_fps()

            # ── Renderizar ──
            if dirty or frame_count % 5 == 0:  # Redibujar al menos cada 5 frames
                self._render()
                self.screen.flip()

            frame_count += 1

        self.cleanup()
        return 0

    def _dispatch_touch(self, screen_x: int, screen_y: int) -> None:
        """Despacha un evento tactil al primer widget que lo acepte."""
        for widget in self._interactive_widgets:
            if widget.hit_test(screen_x, screen_y):
                widget.on_touch(screen_x, screen_y)
                break

    def _handle_touch_down(self, screen_x: int, screen_y: int) -> None:
        """Manejador de touch down desde el driver evdev."""
        self._dispatch_touch(screen_x, screen_y)

    def _handle_touch_up(self, screen_x: int, screen_y: int) -> None:
        """Manejador de touch up desde el driver evdev."""
        pass  # Los widgets manejan solo touch-down por simplicidad

    def _handle_touch_move(self, screen_x: int, screen_y: int) -> None:
        """Manejador de touch move desde el driver evdev."""
        pass  # No se usa arrastre en esta UI

    def _apply_ws_state(self) -> bool:
        """Aplica el estado recibido via WebSocket a los widgets.

        Solo debe llamarse desde el hilo principal. Devuelve True si hubo cambios.
        """
        changed = False
        with self._ws_lock:
            if not self._ws_dirty:
                return False
            self._ws_dirty = False
            # Copiar estado bajo lock
            led_on = self.led_on
            led_label = self.led_label
            press_count = self.press_count

        # Fuera del lock: aplicar a widgets (solo hilo principal)
        if self.led.on != led_on or self.led.label != led_label:
            self.led.on = led_on
            self.led.label = led_label
            changed = True
        if self.button.press_count != press_count:
            self.button.press_count = press_count
            changed = True
        return changed

    # ── Limpieza ────────────────────────────────────────────────

    def cleanup(self) -> None:
        """Limpia todos los recursos."""
        self.running = False
        logger.info("Cerrando display app...")
        if self.touch:
            self.touch.close()
        self.screen.cleanup()
        logger.info("Display app cerrada")


# ═══════════════════════════════════════════════════════════════
# Punto de entrada
# ═══════════════════════════════════════════════════════════════


def _configure_logging(debug: bool = False) -> None:
    """Configura el logging de la aplicacion."""
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    # Silenciar logs muy verbosos de librerias
    logging.getLogger("websocket").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)


def _signal_handler(signum: int, frame: object) -> None:
    """Manejador de señales para shutdown graceful."""
    logger.info("Señal %s recibida, cerrando...", signum)
    # La app se cierra en el siguiente tick del bucle


def main() -> int:
    """Punto de entrada CLI."""
    parser = argparse.ArgumentParser(
        description="Display app Pygame DRM para Raspberry Pi HMI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python display/app.py                           # Auto-deteccion en Pi
  python display/app.py --mock                    # Modo desarrollo (ventana)
  python display/app.py --api-url http://192.168.88.211:8000
  python display/app.py --fps 15 --touch-device /dev/input/event1
        """,
    )
    parser.add_argument(
        "--api-url",
        default="http://localhost:8000",
        help="URL base de la API REST (default: http://localhost:8000)",
    )
    parser.add_argument(
        "--touch-device",
        default=None,
        help="Dispositivo táctil (default: auto-detect)",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Forzar modo mock (ventana en PC, sin DRM)",
    )
    parser.add_argument(
        "--no-mock",
        action="store_true",
        help="Forzar modo real (DRM/KMS), incluso en PC",
    )
    parser.add_argument(
        "--no-touch",
        action="store_true",
        help="Desactivar soporte táctil",
    )
    parser.add_argument(
        "--fps",
        type=int,
        default=20,
        help="FPS objetivo (default: 20)",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Activar logging DEBUG",
    )
    args = parser.parse_args()

    _configure_logging(args.debug)

    # ── Deteccion automatica de mock en PC ──
    is_linux = platform.system() == "Linux"
    use_mock = args.mock or (not is_linux and not args.no_mock)
    if use_mock and not args.mock:
        logger.info("Auto-mock: sistema %s (usa --no-mock para forzar DRM)", platform.system())

    # Registrar manejador de señales
    signal.signal(signal.SIGINT, lambda s, f: _signal_handler(s, f))
    signal.signal(signal.SIGTERM, lambda s, f: _signal_handler(s, f))

    logger.info("=" * 50)
    logger.info("  RPi HMI — Display App Pygame DRM v0.1")
    logger.info("=" * 50)

    # Verificar que el backend esta accesible
    try:
        resp = requests.get(f"{args.api_url.rstrip('/')}/health", timeout=2)
        if resp.status_code == 200:
            logger.info("Backend detectado en %s ✓", args.api_url)
        else:
            logger.warning("Backend respondio con status %d", resp.status_code)
    except requests.RequestException:
        logger.warning("Backend no accesible en %s — la app funcionara offline", args.api_url)

    app = DisplayApp(
        api_url=args.api_url,
        touch_device=args.touch_device,
        mock=use_mock,
        no_touch=args.no_touch,
        fps=args.fps,
    )

    try:
        return app.run()
    except KeyboardInterrupt:
        logger.info("Interrumpido por el usuario")
        app.cleanup()
        return 0
    except Exception as exc:
        logger.exception("Error fatal: %s", exc)
        app.cleanup()
        return 1


if __name__ == "__main__":
    sys.exit(main())
