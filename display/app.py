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
import queue
import signal
import sys
import threading
import time
from collections.abc import Callable
from pathlib import Path

import requests

# ── Pygame import (puede fallar en PC sin pygame instalado) ──
try:
    import pygame  # noqa: E402
except ImportError:
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
from display.ui.widgets import (  # noqa: E402
    ButtonWidget,
    ConfigButton,
    ConfigOverlay,
    FontSettingsView,
    HeaderWidget,
    LedIndicator,
    NetworkConfigView,
    ScreenTestView,
    SecuritySettingsView,
    StatusBar,
    TouchCalibrationView,
    apply_font_settings,
)

logger = logging.getLogger("rpi_hmi.display")


def _load_version() -> str:
    """Lee la version de la aplicacion desde VERSION (raiz del repo)."""
    version_path = Path(__file__).resolve().parents[1] / "VERSION"
    try:
        return version_path.read_text(encoding="utf-8").strip()
    except OSError:
        return "0.4.0"


__version__ = _load_version()

# Referencia global a la instancia activa para shutdown graceful por señales
_app_instance: DisplayApp | None = None


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
        self.press_count: int = 0
        self.backend_connected: bool = False
        self.ws_connected: bool = False
        self._last_sync: float = 0.0
        self._sync_interval: float = 3.0  # Solo como fallback cuando WS cae

        # V1.1: sistema de vistas
        # "main" | "config" | "screen_test" | "touch_calib" | "network" | "font" | "security"
        self.view: str = "main"

        # Control de redibujado (event-driven) y calibración
        self._redraw: bool = False
        self._calib_done_time: float | None = None
        self._calib_samples: list[tuple[int, int]] | None = None
        self._pending_display_action: str | None = None
        self._pending_font_family: str | None = None
        self._pending_text_size: str | None = None

        # Feedback no-bloqueante del boton: frame actual y duracion en frames
        self._button_press_frame: int = -1
        self._button_press_duration: int = 2

        # Screen (se inicializa después de saber mock)
        # En modo real (no --mock) NO permitimos fallback silencioso a mock:
        # si DRM falla, init() devuelve False → run() devuelve 1 → systemd reinicia.
        self.screen = Screen(
            auto_detect=not mock,
            mock=mock,
            allow_mock_fallback=mock,
        )

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

        # REST worker thread (peticiones HTTP no bloqueantes)
        self._rest_queue: queue.Queue = queue.Queue()
        self._rest_ui_queue: queue.Queue = queue.Queue()
        self._rest_thread: threading.Thread | None = None
        self._rest_stop = threading.Event()

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
        self.header = HeaderWidget(0, 0, w, header_h, version=__version__)

        # Content area
        content_y = header_h + margin
        content_h = h - header_h - footer_h - margin * 2

        # Panel LED (izquierda)
        led_x = int(LED_PANEL_X * sx)
        led_w = int(LED_PANEL_W * sx)
        self.led = LedIndicator(led_x, content_y, led_w, content_h, label="INTERRUPTOR ON/OFF")

        # Panel Botón (derecha)
        btn_w = int(BTN_PANEL_W * sx)
        btn_x = w - btn_w - int(margin * sx)
        self.button = ButtonWidget(btn_x, content_y, btn_w, content_h, label="PULSADOR")

        # Footer
        self.status_bar = StatusBar(0, h - footer_h, w, footer_h)

        # V1.1: Config button (flotante, esquina inferior derecha)
        self.config_btn = ConfigButton(w, h)

        # V1.1: Pantallas de configuración
        self.config_overlay = ConfigOverlay(w, h)
        self.screen_test_view = ScreenTestView(w, h)
        self.touch_calib_view = TouchCalibrationView(w, h)
        self.network_view = NetworkConfigView(w, h)
        self.font_view = FontSettingsView(w, h)
        self.security_view = SecuritySettingsView(w, h)

        # Conectar callbacks
        self.led.set_on_toggle(self._on_toggle_led)
        self.button.set_on_press(self._on_press_button)
        self.button.set_on_release(self._on_release_button)
        self.config_btn.set_on_click(self._show_config)
        self.config_overlay.set_callbacks(
            self._show_screen_test,
            self._show_touch_calib,
            self._show_network,
            self._show_font,
            self._show_security,
            self._show_main,
        )
        self.screen_test_view.set_on_exit(self._show_config)
        self.network_view.set_on_apply(self._apply_network)
        self.network_view.set_on_back(self._show_config)
        self.font_view.set_on_change(self._apply_font_settings)
        self.font_view.set_on_back(self._show_config)
        self.security_view.set_on_back(self._show_config)
        self.security_view.set_on_toggle(self._toggle_security)
        self.security_view.set_on_change(self._change_password)

        # Lista de widgets interactivos (orden de hit-test) — vista principal
        self._interactive_widgets = [self.button, self.led, self.config_btn]

        # Lista de todos los widgets a dibujar — vista principal
        self._all_widgets = [self.header, self.led, self.button, self.status_bar, self.config_btn]

    # ── Callbacks de widgets ────────────────────────────────────

    def _on_toggle_led(self) -> None:
        """Callback: el usuario tocó el botón toggle del LED."""
        logger.debug("Toggle LED solicitado")
        self._api_post("/api/led/toggle")
        # Sync inmediato para reflejar el cambio
        self._sync_state()

    def _on_press_button(self) -> None:
        """Callback: el usuario tocó el botón principal (down)."""
        logger.debug("Button press solicitado")
        self.button.pressed = True
        self._button_press_frame = 0
        self._api_post("/api/button/press")
        self._sync_state()
        self._redraw = True

    def _on_release_button(self) -> None:
        """Callback: el usuario soltó el botón principal (up)."""
        logger.debug("Button release solicitado")
        self.button.pressed = False
        self._api_post("/api/button/release")
        self._redraw = True

    # V1.1: Callbacks de cambio de vista

    def _show_config(self) -> None:
        """Muestra el menú de configuración."""
        self.view = "config"
        self._redraw = True

    def _show_main(self) -> None:
        """Vuelve a la vista principal."""
        self.view = "main"
        self._redraw = True

    def _show_screen_test(self) -> None:
        """Muestra la prueba de pantalla."""
        self.view = "screen_test"
        self._redraw = True

    def _show_touch_calib(self) -> None:
        """Muestra la calibración táctil."""
        self.touch_calib_view.reset()
        self._calib_done_time = None
        self._calib_samples = None
        self.view = "touch_calib"
        self._redraw = True

    def _show_network(self) -> None:
        """Muestra la configuración de red y carga el estado actual."""
        self.network_view.set_result("")
        self.view = "network"
        self._redraw = True
        self._fetch_network()

    def _fetch_network(self) -> None:
        """Carga el estado de red actual desde el backend (no bloqueante)."""
        def apply(data: dict | None) -> None:
            if data is not None:
                self.network_view.set_status(data)
                self._redraw = True

        self._api_get("/api/network", on_result=apply)

    def _apply_network(self, payload: dict) -> None:
        """Aplica la configuracion de red (estatica o DHCP) en background."""
        mode = payload.get("mode")

        def apply(result: dict | None) -> None:
            if result is not None:
                ok = result.get("success", False)
                msg = result.get("message", "")
                self.network_view.set_result(msg, error=not ok)
            else:
                self.network_view.set_result("No se pudo aplicar la configuracion", error=True)
            self._redraw = True

        if mode == "static":
            self._api_post_json(
                "/api/network/static",
                {
                    "ip_address": payload["ip_address"],
                    "prefix": payload["prefix"],
                    "gateway": payload["gateway"],
                    "dns": payload["dns"],
                },
                on_result=apply,
            )
        else:
            self._api_post("/api/network/dhcp", on_result=apply)

    def _show_font(self) -> None:
        """Muestra la configuracion de fuente y carga el estado actual."""
        self.view = "font"
        self._redraw = True
        self._fetch_font_settings()

    def _fetch_font_settings(self) -> None:
        """Carga los ajustes de fuente desde el backend (no bloqueante)."""
        def apply(data: dict | None) -> None:
            if data is not None:
                family = data.get("font_family", "dejavu")
                size = data.get("text_size", "medium")
                self.font_view.set_selection(family, size)
                self._redraw = True

        self._api_get("/api/settings/display", on_result=apply)

    def _apply_font_settings(self, font_family: str, text_size: str) -> None:
        """Aplica y persiste los ajustes de fuente (desde display o web)."""
        apply_font_settings(font_family, text_size)
        self.font_view.set_selection(font_family, text_size)
        self._api_post_json(
            "/api/settings/display",
            {"font_family": font_family, "text_size": text_size},
        )
        self._redraw = True

    def _show_security(self) -> None:
        """Muestra la configuracion de contraseña y carga el estado actual."""
        self.security_view.set_result("")
        self.view = "security"
        self._redraw = True
        self._fetch_security()

    def _fetch_security(self) -> None:
        """Carga el estado de seguridad actual desde el backend (no bloqueante)."""
        def apply(data: dict | None) -> None:
            if data is not None:
                self.security_view.set_status(data)
                self._redraw = True

        self._api_get("/api/auth/security", on_result=apply)

    def _toggle_security(self, enabled: bool, current: str) -> None:
        """Activa o desactiva la proteccion por contraseña en background."""
        def apply(result: dict | None) -> None:
            if result is not None:
                self.security_view.set_status(result)
                self.security_view.set_result(
                    "Proteccion activada" if enabled else "Proteccion desactivada",
                )
                self.security_view.clear_fields()
                self._fetch_security()
            else:
                self.security_view.set_result(
                    "No se pudo aplicar (contraseña actual incorrecta)", error=True
                )
            self._redraw = True

        self._api_post_json(
            "/api/auth/security",
            {"enabled": enabled, "current": current},
            on_result=apply,
        )

    def _change_password(self, current: str, new: str) -> None:
        """Cambia la contraseña del panel en background."""
        def apply(result: dict | None) -> None:
            if result is not None:
                self.security_view.set_result("Contraseña actualizada")
                self.security_view.clear_fields()
                self._fetch_security()
            else:
                self.security_view.set_result(
                    "No se pudo cambiar (contraseña actual incorrecta)", error=True
                )
            self._redraw = True

        self._api_post_json(
            "/api/auth/password",
            {"current": current, "new": new},
            on_result=apply,
        )

    def _register_calib_tap(self, raw_x: int, raw_y: int) -> None:
        """Registra un toque de calibración usando coordenadas RAW."""
        self.touch_calib_view.register_tap(raw_x, raw_y)
        if self.touch_calib_view.is_done:
            coeffs = self.touch_calib_view.coefficients
            if coeffs and self.touch:
                self.touch.set_calibration_from_points(self.touch_calib_view.raw_points)
                logger.info("Calibración táctil aplicada: %s", coeffs)
                self._calib_done_time = time.time()
            else:
                logger.warning("Calibración fallida — reintentando")
                self.touch_calib_view.reset()
        self._redraw = True

    # ── Comunicacion con backend ────────────────────────────────

    def _api_get(
        self,
        endpoint: str,
        on_result: Callable[[dict | None], None] | None = None,
    ) -> None:
        """Encola un GET al backend REST (no bloqueante)."""
        self._rest_queue.put(("get", endpoint, None, on_result))
        self._start_rest_worker()

    def _api_post(
        self,
        endpoint: str,
        on_result: Callable[[dict | None], None] | None = None,
    ) -> None:
        """Encola un POST al backend REST (no bloqueante)."""
        self._rest_queue.put(("post", endpoint, None, on_result))
        self._start_rest_worker()

    def _api_post_json(
        self,
        endpoint: str,
        payload: dict,
        on_result: Callable[[dict | None], None] | None = None,
    ) -> None:
        """Encola un POST con body JSON al backend REST (no bloqueante)."""
        self._rest_queue.put(("post_json", endpoint, payload, on_result))
        self._start_rest_worker()

    def _start_rest_worker(self) -> None:
        """Arranca el worker thread de REST si no esta activo."""
        if self._rest_thread is not None and self._rest_thread.is_alive():
            return
        self._rest_stop.clear()
        self._rest_thread = threading.Thread(
            target=self._rest_worker_loop,
            daemon=True,
            name="display-rest",
        )
        self._rest_thread.start()
        logger.info("REST worker thread iniciado")

    def _rest_worker_loop(self) -> None:
        """Bucle del worker que ejecuta peticiones REST en background."""
        while not self._rest_stop.is_set():
            try:
                kind, endpoint, payload, on_result = self._rest_queue.get(timeout=0.5)
            except queue.Empty:
                continue
            try:
                if kind == "get":
                    result = self._request_get(endpoint)
                elif kind == "post":
                    result = self._request_post(endpoint)
                else:
                    result = self._request_post_json(endpoint, payload)
            except Exception as exc:
                logger.warning("REST worker error en %s: %s", endpoint, exc)
                result = None
            finally:
                self._rest_queue.task_done()

            if on_result is not None:
                self._rest_ui_queue.put((on_result, result))

    def _request_get(self, endpoint: str) -> dict | None:
        """GET bloqueante ejecutado en el worker thread."""
        try:
            resp = requests.get(f"{self.api_url}{endpoint}", timeout=2)
            resp.raise_for_status()
            with self._ws_lock:
                self.backend_connected = True
            return resp.json()
        except requests.RequestException:
            with self._ws_lock:
                self.backend_connected = False
            return None

    def _request_post(self, endpoint: str) -> dict | None:
        """POST bloqueante ejecutado en el worker thread."""
        try:
            resp = requests.post(f"{self.api_url}{endpoint}", timeout=2)
            resp.raise_for_status()
            with self._ws_lock:
                self.backend_connected = True
            return resp.json()
        except requests.RequestException:
            with self._ws_lock:
                self.backend_connected = False
            return None

    def _request_post_json(self, endpoint: str, payload: dict) -> dict | None:
        """POST JSON bloqueante ejecutado en el worker thread."""
        try:
            resp = requests.post(
                f"{self.api_url}{endpoint}",
                json=payload,
                timeout=5,
            )
            resp.raise_for_status()
            with self._ws_lock:
                self.backend_connected = True
            return resp.json()
        except requests.RequestException as exc:
            with self._ws_lock:
                self.backend_connected = False
            logger.warning("POST %s fallo: %s", endpoint, exc)
            return None

    def _apply_rest_results(self) -> None:
        """Aplica en el hilo principal los resultados pendientes del worker."""
        while True:
            try:
                on_result, result = self._rest_ui_queue.get_nowait()
            except queue.Empty:
                break
            try:
                on_result(result)
            except Exception as exc:
                logger.warning("Error aplicando resultado REST: %s", exc)

    def _sync_state(self) -> None:
        """Encola una sincronizacion del estado local con el backend via REST."""

        def apply(data: dict | None) -> None:
            if data is None:
                return
            led_data = data.get("led", {})
            btn_data = data.get("button", {})

            new_led_on = led_data.get("state", self.led_on)
            new_press_count = btn_data.get("press_count", self.press_count)
            new_ws_connected = data.get("websocket_clients", 0) > 0

            with self._ws_lock:
                self.led_on = new_led_on
                self.press_count = new_press_count
                self.ws_connected = new_ws_connected

            if self.led.on != new_led_on:
                self.led.on = new_led_on
                self._redraw = True
            if self.button.press_count != new_press_count:
                self.button.press_count = new_press_count
                self._redraw = True

        self._api_get("/api/status", on_result=apply)

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
            ws.send(
                json.dumps({"type": "subscribe", "topics": ["led", "button", "display"], "version": "1.0"})
            )

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
                elif msg_type == "button_pressed":
                    self.press_count = data.get("press_count", self.press_count)
                elif msg_type == "status_update":
                    led_d = data.get("led", {})
                    btn_d = data.get("button", {})
                    self.led_on = led_d.get("state", self.led_on)
                    self.press_count = btn_d.get("press_count", self.press_count)
                elif msg_type == "display_command":
                    self._pending_display_action = data.get("action", "")
                elif msg_type == "display_settings_changed":
                    self._pending_font_family = data.get("font_family", "")
                    self._pending_text_size = data.get("text_size", "")
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
        """Renderiza todos los widgets según la vista actual."""
        surface = self.screen.get_surface()
        self.screen.clear()

        if self.view == "main":
            for widget in self._all_widgets:
                widget.draw(surface)
        elif self.view == "config":
            self.config_overlay.draw(surface)
        elif self.view == "screen_test":
            self.screen_test_view.draw(surface)
        elif self.view == "touch_calib":
            self.touch_calib_view.draw(surface)
        elif self.view == "network":
            self.network_view.draw(surface)
        elif self.view == "font":
            self.font_view.draw(surface)
        elif self.view == "security":
            self.security_view.draw(surface)

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

        # Cargar y aplicar ajustes de fuente desde el backend (no bloqueante)
        def _apply_loaded_font(data: dict | None) -> None:
            if data is None:
                return
            family = data.get("font_family", "dejavu")
            size = data.get("text_size", "medium")
            try:
                apply_font_settings(family, size)
            except Exception as exc:
                logger.warning("No se pudieron cargar ajustes de fuente: %s", exc)
                return
            self.font_view.set_selection(family, size)
            logger.info("Ajustes de fuente aplicados: %s / %s", family, size)

        self._api_get("/api/settings/display", on_result=_apply_loaded_font)

        # Auto-iniciar calibración táctil si no hay calibración guardada
        if self.touch and self.touch.available and not self.touch.has_calibration:
            self.view = "touch_calib"
            logger.info("Sin calibración táctil — iniciando asistente de calibración")

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

        self._last_second = -1

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
                if self.screen.mock and event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                    self._handle_touch_up(event.pos[0], event.pos[1])

            if not self.running:
                break

            # ── Eventos touch (evdev) ──
            if self.touch and self.touch.available:
                self.touch.poll()

            # ── Feedback no-bloqueante del boton: auto-liberacion por frames ──
            if self._button_press_frame >= 0:
                self._button_press_frame += 1
                if self._button_press_frame >= self._button_press_duration:
                    if self.button.pressed:
                        self._on_release_button()
                    self._button_press_frame = -1

            # ── Aplicar resultados de peticiones REST (worker) ──
            self._apply_rest_results()

            # Consumir flag de redibujado establecido por callbacks
            if self._redraw:
                dirty = True
                self._redraw = False

            # ── Aplicar estado recibido via WebSocket ──
            if self._apply_ws_state():
                dirty = True

            # ── Sincronizacion periodica con backend (solo si WS no conectado) ──
            now = time.time()
            if now - self._last_sync > self._sync_interval:
                with self._ws_lock:
                    ws_ok = self.ws_connected
                if not ws_ok:
                    self._sync_state()
                self._last_sync = now

            # ── Actualizar status bar (solo en vista principal) ──
            if self.view == "main":
                self.status_bar.time_str = time.strftime("%H:%M:%S")
                with self._ws_lock:
                    self.status_bar.backend_connected = self.backend_connected
                    self.status_bar.ws_connected = self.ws_connected
                self.status_bar.fps = self.screen.get_fps()
                # Redibujar 1x por segundo para actualizar el reloj
                if int(now) != self._last_second:
                    self._last_second = int(now)
                    dirty = True

            # ── Auto-volver tras calibración ──
            if (
                self.view == "touch_calib"
                and self.touch_calib_view.is_done
                and self._calib_done_time
                and now - self._calib_done_time > 2.5
            ):
                self._show_main()

            # ── Renderizar solo cuando hay cambios ──
            if dirty:
                self._render()
                self.screen.flip()

        self.cleanup()
        return 0

    def _dispatch_touch(self, screen_x: int, screen_y: int) -> None:
        """Despacha un evento táctil según la vista actual."""
        logger.debug("Touch dispatch: view=%s screen=(%d,%d)", self.view, screen_x, screen_y)
        if self.view == "main":
            for widget in self._interactive_widgets:
                if widget.hit_test(screen_x, screen_y):
                    widget.on_touch(screen_x, screen_y)
                    break
        elif self.view == "config":
            self.config_overlay.on_touch(screen_x, screen_y)
        elif self.view == "screen_test":
            self.screen_test_view.on_touch(screen_x, screen_y)
        elif self.view == "network":
            self.network_view.on_touch(screen_x, screen_y)
        elif self.view == "font":
            self.font_view.on_touch(screen_x, screen_y)
        elif self.view == "security":
            self.security_view.on_touch(screen_x, screen_y)
        elif self.view == "touch_calib":
            # Solo se alcanza en modo mock (mouse): simula raw con pantalla
            self._register_calib_tap(screen_x, screen_y)
        self._redraw = True

    def _handle_touch_down(self, screen_x: int, screen_y: int) -> None:
        """Manejador de touch down desde el driver evdev."""
        if self.view == "touch_calib":
            # Modo calibración: acumular muestras raw durante el toque
            self._calib_samples = [(self.touch.x, self.touch.y)]
            return
        self._dispatch_touch(screen_x, screen_y)

    def _handle_touch_up(self, screen_x: int, screen_y: int) -> None:
        """Manejador de touch up desde el driver evdev."""
        # En calibración: usar la mediana de las muestras raw (rechaza el
        # primer valor no estabilizado del panel resistivo).
        if self.view == "touch_calib" and self._calib_samples is not None:
            samples = self._calib_samples
            self._calib_samples = None
            xs = sorted(x for x, _y in samples)
            ys = sorted(y for _x, y in samples)
            mx = xs[len(xs) // 2]
            my = ys[len(ys) // 2]
            logger.info(
                "Calib samples=%d -> median raw=(%d,%d)", len(samples), mx, my,
            )
            self._register_calib_tap(mx, my)
            return
        # Liberar el boton PULSAR si estaba presionado en la vista principal
        if self.view == "main" and self.button.pressed:
            self._on_release_button()

    def _handle_touch_move(self, screen_x: int, screen_y: int) -> None:
        """Manejador de touch move desde el driver evdev."""
        # En calibración: acumular muestras raw para estabilizar el toque
        if self.view == "touch_calib" and self._calib_samples is not None:
            self._calib_samples.append((self.touch.x, self.touch.y))

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
            press_count = self.press_count
            pending_action = self._pending_display_action
            self._pending_display_action = None
            pending_family = self._pending_font_family
            self._pending_font_family = None
            pending_size = self._pending_text_size
            self._pending_text_size = None

        # Fuera del lock: aplicar a widgets (solo hilo principal)
        if self.led.on != led_on:
            self.led.on = led_on
            changed = True
        if self.button.press_count != press_count:
            self.button.press_count = press_count
            changed = True

        # Aplicar ajustes de fuente recibidos desde el backend/web
        if pending_family and pending_size:
            apply_font_settings(pending_family, pending_size)
            self.font_view.set_selection(pending_family, pending_size)
            changed = True

        # Aplicar comando de cambio de vista desde el backend/web
        if pending_action:
            self._set_view_from_command(pending_action)
            changed = True

        return changed

    def _set_view_from_command(self, action: str) -> None:
        """Cambia la vista segun el comando recibido del backend/web."""
        mapping = {
            "screen_test": self._show_screen_test,
            "touch_calib": self._show_touch_calib,
            "network": self._show_network,
            "font": self._show_font,
            "security": self._show_security,
            "config": self._show_config,
            "main": self._show_main,
        }
        handler = mapping.get(action)
        if handler:
            logger.info("Comando de vista: %s", action)
            handler()
        else:
            logger.warning("Comando de vista desconocido: %s", action)

    # ── Limpieza ────────────────────────────────────────────────

    def cleanup(self) -> None:
        """Limpia todos los recursos."""
        self.running = False
        stop = getattr(self, "_rest_stop", None)
        if stop is not None:
            stop.set()
        logger.info("Cerrando display app...")
        if self.touch:
            self.touch.close()
        self.screen.cleanup()
        rest_thread = getattr(self, "_rest_thread", None)
        if rest_thread is not None:
            rest_thread.join(timeout=1.0)
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
    if _app_instance is not None:
        _app_instance.running = False


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
    logger.info("  RPi HMI — Display App Pygame DRM v%s", __version__)
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

    global _app_instance
    _app_instance = app

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
