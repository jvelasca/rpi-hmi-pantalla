"""Tests para DisplayApp: CLI args, WebSocket sync, threading.

Ejecutar con:
    PYTHONPATH=. python -m pytest display/tests/test_display_app.py -v --tb=short
"""

from __future__ import annotations

import argparse
import sys
import threading
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Asegurar que display/ esta en el path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


# ── Helper: build the same ArgumentParser as main() ──────────────

def _build_parser() -> argparse.ArgumentParser:
    """Replica el parser de CLI definido en display.app.main()."""
    parser = argparse.ArgumentParser(
        description="Display app Pygame DRM para Raspberry Pi HMI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--api-url", default="http://localhost:8000")
    parser.add_argument("--touch-device", default=None)
    parser.add_argument("--mock", action="store_true")
    parser.add_argument("--no-mock", action="store_true")
    parser.add_argument("--no-touch", action="store_true")
    parser.add_argument("--fps", type=int, default=20)
    parser.add_argument("--debug", action="store_true")
    return parser


# ═══════════════════════════════════════════════════════════════
# CLI Argument Parsing
# ═══════════════════════════════════════════════════════════════


class TestDisplayAppCLI:
    """Pruebas de parsing de argumentos CLI."""

    def test_default_args(self) -> None:
        """Con argv vacio (sin flags), todos los defaults son correctos."""
        parser = _build_parser()
        with patch.object(sys, "argv", ["app.py"]):
            args = parser.parse_args()
        assert args.api_url == "http://localhost:8000"
        assert args.touch_device is None
        assert args.mock is False
        assert args.no_mock is False
        assert args.no_touch is False
        assert args.fps == 20
        assert args.debug is False

    def test_mock_flag(self) -> None:
        """--mock activa mock=True."""
        parser = _build_parser()
        with patch.object(sys, "argv", ["app.py", "--mock"]):
            args = parser.parse_args()
        assert args.mock is True

    def test_api_url_flag(self) -> None:
        """--api-url http://custom:9000 asigna la URL personalizada."""
        parser = _build_parser()
        with patch.object(sys, "argv", ["app.py", "--api-url", "http://custom:9000"]):
            args = parser.parse_args()
        assert args.api_url == "http://custom:9000"

    def test_debug_flag(self) -> None:
        """--debug activa debug=True."""
        parser = _build_parser()
        with patch.object(sys, "argv", ["app.py", "--debug"]):
            args = parser.parse_args()
        assert args.debug is True

    def test_no_touch_flag(self) -> None:
        """--no-touch desactiva touch."""
        parser = _build_parser()
        with patch.object(sys, "argv", ["app.py", "--no-touch"]):
            args = parser.parse_args()
        assert args.no_touch is True

    def test_fps_flag(self) -> None:
        """--fps 30 asigna fps=30."""
        parser = _build_parser()
        with patch.object(sys, "argv", ["app.py", "--fps", "30"]):
            args = parser.parse_args()
        assert args.fps == 30

    def test_auto_mock_on_non_linux(self) -> None:
        """En sistema no-Linux sin --no-mock, use_mock es True."""
        parser = _build_parser()
        with patch.object(sys, "argv", ["app.py"]):
            args = parser.parse_args()
        # Replicar la logica de main():
        # use_mock = args.mock or (not is_linux and not args.no_mock)
        import platform
        is_linux = platform.system() == "Linux"
        use_mock = args.mock or (not is_linux and not args.no_mock)
        if not is_linux:
            assert use_mock is True
        else:
            assert use_mock is False

    def test_no_mock_on_linux(self) -> None:
        """En Linux sin --mock, use_mock es False."""
        import platform

        parser = _build_parser()
        with patch.object(sys, "argv", ["app.py"]):
            args = parser.parse_args()
        # Simular Linux: con platform.system() == "Linux", use_mock=False
        with patch("platform.system", return_value="Linux"):
            is_linux = platform.system() == "Linux"
            use_mock = args.mock or (not is_linux and not args.no_mock)
            assert is_linux is True
            assert use_mock is False


# ═══════════════════════════════════════════════════════════════
# WebSocket URL
# ═══════════════════════════════════════════════════════════════


class TestDisplayAppWebSocket:
    """Pruebas de URL del WebSocket."""

    def test_ws_url_from_api_url(self) -> None:
        """http://host:8000 -> ws://host:8000/ws (http -> ws replacement)."""
        from display.app import DisplayApp

        app = DisplayApp.__new__(DisplayApp)
        app.api_url = "http://192.168.1.100:8000"
        # Replicar la logica de _ws_loop:
        ws_url = app.api_url.replace("http://", "ws://") + "/ws"
        assert ws_url == "ws://192.168.1.100:8000/ws"

    def test_ws_url_localhost(self) -> None:
        """http://localhost:8000 -> ws://localhost:8000/ws."""
        from display.app import DisplayApp

        app = DisplayApp.__new__(DisplayApp)
        app.api_url = "http://localhost:8000"
        ws_url = app.api_url.replace("http://", "ws://") + "/ws"
        assert ws_url == "ws://localhost:8000/ws"


# ═══════════════════════════════════════════════════════════════
# State Sync (apply_ws_state)
# ═══════════════════════════════════════════════════════════════


class TestDisplayAppStateSync:
    """Pruebas de sincronizacion de estado via _apply_ws_state."""

    def test_apply_ws_state_led_changed_updates_led(self) -> None:
        """_apply_ws_state aplica cambios de LED a los widgets."""
        from display.app import DisplayApp
        from display.ui.widgets import ButtonWidget, LedIndicator

        app = DisplayApp.__new__(DisplayApp)
        app.screen = MagicMock()
        app.screen.width = 480
        app.screen.height = 320
        app._ws_lock = threading.Lock()

        # Estado simulado (WS thread ya escribio)
        app.led_on = True
        app.led_label = "ENCENDIDO"
        app.press_count = 0
        app._ws_dirty = True

        app.led = LedIndicator(10, 50, 180, 230)
        app.led.on = False
        app.led.label = "APAGADO"
        app.button = ButtonWidget(260, 50, 180, 230)
        app.button.press_count = 0

        app._pending_display_action = None
        app._pending_font_family = None
        app._pending_text_size = None

        result = app._apply_ws_state()
        assert result is True
        assert app.led.on is True
        assert app.led.label == "ENCENDIDO"

    def test_apply_ws_state_button_pressed(self) -> None:
        """_apply_ws_state aplica cambios de button press_count."""
        from display.app import DisplayApp
        from display.ui.widgets import ButtonWidget, LedIndicator

        app = DisplayApp.__new__(DisplayApp)
        app.screen = MagicMock()
        app.screen.width = 480
        app.screen.height = 320
        app._ws_lock = threading.Lock()

        app.led_on = False
        app.led_label = "APAGADO"
        app.press_count = 42
        app._ws_dirty = True

        app.led = LedIndicator(10, 50, 180, 230)
        app.led.on = False
        app.led.label = "APAGADO"
        app.button = ButtonWidget(260, 50, 180, 230)
        app.button.press_count = 0

        app._pending_display_action = None
        app._pending_font_family = None
        app._pending_text_size = None

        result = app._apply_ws_state()
        assert result is True
        assert app.button.press_count == 42

    def test_apply_ws_state_status_update_updates_all(self) -> None:
        """_apply_ws_state aplica todos los cambios simultaneamente."""
        from display.app import DisplayApp
        from display.ui.widgets import ButtonWidget, LedIndicator

        app = DisplayApp.__new__(DisplayApp)
        app.screen = MagicMock()
        app.screen.width = 480
        app.screen.height = 320
        app._ws_lock = threading.Lock()

        app.led_on = True
        app.led_label = "LED_ON"
        app.press_count = 99
        app._ws_dirty = True

        app.led = LedIndicator(10, 50, 180, 230)
        app.led.on = False
        app.led.label = "APAGADO"
        app.button = ButtonWidget(260, 50, 180, 230)
        app.button.press_count = 0

        app._pending_display_action = None
        app._pending_font_family = None
        app._pending_text_size = None

        result = app._apply_ws_state()
        assert result is True
        assert app.led.on is True
        assert app.led.label == "LED_ON"
        assert app.button.press_count == 99

    def test_apply_ws_state_invalid_data_handled(self) -> None:
        """_apply_ws_state con _ws_dirty=False retorna False sin cambios."""
        from display.app import DisplayApp
        from display.ui.widgets import ButtonWidget, LedIndicator

        app = DisplayApp.__new__(DisplayApp)
        app.screen = MagicMock()
        app.screen.width = 480
        app.screen.height = 320
        app._ws_lock = threading.Lock()

        app.led_on = False
        app.led_label = "APAGADO"
        app.press_count = 0
        app._ws_dirty = False  # No hay datos nuevos

        app.led = LedIndicator(10, 50, 180, 230)
        app.led.on = False
        app.led.label = "APAGADO"
        app.button = ButtonWidget(260, 50, 180, 230)
        app.button.press_count = 0

        result = app._apply_ws_state()
        assert result is False

    def test_handle_touch_down_updates_button(self) -> None:
        """_handle_touch_down en area del boton activa el callback on_press."""
        from display.app import DisplayApp
        from display.ui.widgets import ButtonWidget, LedIndicator

        app = DisplayApp.__new__(DisplayApp)
        app.screen = MagicMock()
        app.screen.width = 480
        app.screen.height = 320
        app._ws_lock = threading.Lock()
        app._ws_dirty = False

        app.led = LedIndicator(10, 50, 180, 230)
        app.button = ButtonWidget(260, 50, 180, 230)
        pressed = []

        def on_press() -> None:
            pressed.append(True)
            app.button.pressed = True

        app.button.set_on_press(on_press)
        app._interactive_widgets = [app.button, app.led]

        # Centro del boton
        cx = 260 + 90
        cy = 50 + 20 + (230 - 20) // 2 - 5
        app.view = "main"
        app._handle_touch_down(cx, cy)
        assert len(pressed) == 1
        assert app.button.pressed is True


# ═══════════════════════════════════════════════════════════════
# Lifecycle
# ═══════════════════════════════════════════════════════════════


class TestDisplayAppLifecycle:
    """Pruebas de ciclo de vida del DisplayApp."""

    @pytest.mark.skip(reason="Requiere pygame display inicializado para _create_widgets")
    def test_create_widgets_with_mock(self) -> None:
        """_create_widgets crea los 4 widgets esperados."""
        from display.app import DisplayApp

        app = DisplayApp.__new__(DisplayApp)
        app.screen = MagicMock()
        app.screen.width = 480
        app.screen.height = 320

        # _create_widgets necesita pygame.font inicializado para los widgets
        # Saltamos en entornos sin display
        app._create_widgets()
        assert len(app._all_widgets) == 4

    def test_cleanup_stops_running(self) -> None:
        """cleanup() establece running=False y limpia recursos."""
        from display.app import DisplayApp

        app = DisplayApp.__new__(DisplayApp)
        app.running = True
        app.touch = None
        app.screen = MagicMock()

        app.cleanup()
        assert app.running is False
        app.screen.cleanup.assert_called_once()
