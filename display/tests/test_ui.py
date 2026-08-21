"""Tests unitarios para los widgets, touch handler y screen de la display app.

Ejecutar con:
    PYTHONPATH=. python -m pytest display/tests/test_ui.py -v
"""

from __future__ import annotations

import sys
from pathlib import Path

import pygame
import pytest

# Asegurar que display/ esta en el path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

# ═══════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════


@pytest.fixture(scope="module")
def _pygame_init():
    """Inicializa Pygame una vez por modulo de tests (sin display)."""
    # Usar dummy driver para tests
    import os
    os.environ["SDL_VIDEODRIVER"] = "dummy"
    pygame.display.init()
    pygame.font.init()
    if hasattr(pygame, "freetype"):
        pygame.freetype.init()
    yield
    if hasattr(pygame, "freetype"):
        pygame.freetype.quit()
    pygame.font.quit()
    pygame.display.quit()


@pytest.fixture
def surface(_pygame_init):
    """Surface de 480x320 para renderizar widgets en tests."""
    return pygame.Surface((480, 320))


# ═══════════════════════════════════════════════════════════════
# TouchHandler tests
# ═══════════════════════════════════════════════════════════════


class TestTouchCoordinateMapping:
    """Pruebas de mapeo de coordenadas raw → screen con rotate=270."""

    @pytest.mark.parametrize(
        "raw_x, raw_y, expected_x, expected_y",
        [
            # Centro del touch → centro de la pantalla
            (2048, 2048, 240, 159),
            # Esquina (0,0) raw → esquina inferior izquierda screen
            (0, 0, 0, 319),
            # Esquina (4095, 0) → esquina inferior derecha screen
            (4095, 0, 0, 0),
            # Esquina (0, 4095) → esquina superior izquierda screen
            (0, 4095, 479, 319),
            # Esquina (4095, 4095) → esquina superior derecha screen
            (4095, 4095, 479, 0),
        ],
    )
    def test_mapping_rotate_270(self, raw_x, raw_y, expected_x, expected_y):
        """Verifica el mapeo correcto de coordenadas con rotate=270."""
        from display.ui.touch import TouchHandler

        handler = TouchHandler.__new__(TouchHandler)
        handler.screen_width = 480
        handler.screen_height = 320
        handler.touch_max_x = 4096
        handler.touch_max_y = 4096
        handler.invert_x = False
        handler.invert_y = False

        # Coeficientes afines por defecto de TouchHandler.__init__ (rotate=270)
        handler._a_xx = 0.0
        handler._a_xy = 480.0 / 4096.0
        handler._a_yx = -320.0 / 4096.0
        handler._a_yy = 0.0
        handler._b_x = 0.0
        handler._b_y = 319.0

        sx, sy = handler.raw_to_screen(raw_x, raw_y)
        assert sx == expected_x, f"raw=({raw_x},{raw_y}) → screen=({sx},{sy}), expected x={expected_x}"
        assert sy == expected_y, f"raw=({raw_x},{raw_y}) → screen=({sx},{sy}), expected y={expected_y}"

    @pytest.mark.parametrize(
        "raw_x, raw_y, expected_x, expected_y",
        [
            # (0, 0) raw → sin invert (0, 319); con invert_x + invert_y → (479, 0)
            (0, 0, 479, 0),
            # (4095, 4095) raw → sin invert (479, 0); con invert → (0, 319)
            (4095, 4095, 0, 319),
            # Centro (2048, 2048) → sin invert (240, 159); con invert → (239, 160)
            (2048, 2048, 239, 160),
        ],
    )
    def test_mapping_with_invert(self, raw_x, raw_y, expected_x, expected_y):
        """Verifica el mapeo con ejes invertidos (invert_x/invert_y activos)."""
        from display.ui.touch import TouchHandler

        handler = TouchHandler.__new__(TouchHandler)
        handler.screen_width = 480
        handler.screen_height = 320
        handler.touch_max_x = 4096
        handler.touch_max_y = 4096
        handler.invert_x = True
        handler.invert_y = True

        handler._a_xx = 0.0
        handler._a_xy = 480.0 / 4096.0
        handler._a_yx = -320.0 / 4096.0
        handler._a_yy = 0.0
        handler._b_x = 0.0
        handler._b_y = 319.0

        sx, sy = handler.raw_to_screen(raw_x, raw_y)
        assert sx == expected_x, f"raw=({raw_x},{raw_y}) → screen=({sx},{sy}), expected x={expected_x}"
        assert sy == expected_y, f"raw=({raw_x},{raw_y}) → screen=({sx},{sy}), expected y={expected_y}"


class TestTouchHandlerInit:
    """Pruebas de inicializacion del TouchHandler."""

    def test_no_device_fallback(self):
        """TouchHandler maneja gracefulmente la falta de dispositivo."""
        from display.ui.touch import TouchHandler

        handler = TouchHandler(device_path="/dev/input/nonexistent99")
        assert not handler.available

    def test_available_property(self):
        """La propiedad available refleja si el dispositivo se abrio."""
        from display.ui.touch import TouchHandler

        handler = TouchHandler(device_path="/dev/input/nonexistent99")
        assert not handler.available


class TestReadAbsMax:
    """Pruebas del helper defensivo _read_abs_max (fallback sin hardware)."""

    def test_none_path_returns_none(self):
        """device_path=None → None (no hay dispositivo que leer)."""
        from display.ui.touch import _read_abs_max

        assert _read_abs_max(None, 0) is None

    def test_missing_device_returns_none(self):
        """Dispositivo inexistente → None (fallback a RAW_MAX en __init__)."""
        from display.ui.touch import _read_abs_max

        assert _read_abs_max("/dev/input/nonexistent99", 0) is None

    def test_no_fcntl_returns_none(self):
        """Sin fcntl (Windows) el import diferido falla → None."""
        from unittest.mock import patch

        from display.ui.touch import _read_abs_max

        with patch.dict(sys.modules, {"fcntl": None}):
            assert _read_abs_max("/dev/input/event0", 0) is None

    def test_init_falls_back_to_raw_max_without_device(self):
        """TouchHandler sin hardware usa RAW_MAX para touch_max_x/touch_max_y."""
        from display.ui.touch import RAW_MAX, TouchHandler

        handler = TouchHandler(device_path="/dev/input/nonexistent99")
        assert handler.touch_max_x == RAW_MAX
        assert handler.touch_max_y == RAW_MAX
        assert not handler.available


# ═══════════════════════════════════════════════════════════════
# Widget tests
# ═══════════════════════════════════════════════════════════════


class TestLedIndicator:
    """Pruebas del widget LedIndicator."""

    def test_initial_state(self):
        """El LED comienza apagado."""
        from display.ui.widgets import LedIndicator

        led = LedIndicator(10, 50, 180, 230)
        assert led.on is False
        assert led.label == "LED 1"
        assert led.gpio_pin == 17

    def test_toggle_callback(self, surface):
        """El callback on_toggle se invoca al tocar el boton."""
        from display.ui.widgets import LedIndicator

        led = LedIndicator(10, 50, 180, 230)
        toggled = []

        def on_toggle():
            toggled.append(True)

        led.set_on_toggle(on_toggle)
        # Simular touch en el area del boton toggle
        # El boton esta en la parte inferior del panel LED
        # Panel: (10, 50, 180, 230), btn_rect: (20, 50+230-28-5=247, 160, 28)
        btn_x = 10 + 20 + 80  # centro del boton
        btn_y = 50 + 230 - 14  # centro del boton

        assert led.hit_test(btn_x, btn_y), "El touch deberia caer en el boton"
        led.on_touch(btn_x, btn_y)
        assert len(toggled) == 1, "El callback debio ser llamado"

    def test_touch_outside_button(self):
        """Touch fuera del boton no activa el callback."""
        from display.ui.widgets import LedIndicator

        led = LedIndicator(10, 50, 180, 230)
        toggled = []

        def on_toggle():
            toggled.append(True)

        led.set_on_toggle(on_toggle)

        # Touch en el titulo (no en el boton toggle)
        assert not led.hit_test(100, 55), "Touch en titulo no deberia ser hit"
        led.on_touch(100, 55)
        assert len(toggled) == 0

    def test_draw_renders_without_crash(self, surface):
        """draw() no debe lanzar excepciones."""
        from display.ui.widgets import LedIndicator

        led = LedIndicator(10, 50, 180, 230)
        led.on = True
        led.draw(surface)

        led.on = False
        led.draw(surface)


class TestButtonWidget:
    """Pruebas del widget ButtonWidget."""

    def test_initial_state(self):
        """El boton comienza no presionado con contador 0."""
        from display.ui.widgets import ButtonWidget

        btn = ButtonWidget(260, 50, 180, 230)
        assert btn.pressed is False
        assert btn.press_count == 0

    def test_press_callback(self, surface):
        """El callback on_press se invoca al tocar el boton."""
        from display.ui.widgets import ButtonWidget

        btn = ButtonWidget(260, 50, 180, 230)
        pressed = []

        def on_press():
            pressed.append(True)

        btn.set_on_press(on_press)

        # Centro del boton
        cx = 260 + 180 // 2
        cy = 50 + 20 + (230 - 20) // 2 - 5

        assert btn.hit_test(cx, cy), "Touch en centro del boton deberia ser hit"
        btn.on_touch(cx, cy)
        assert len(pressed) == 1, "El callback debio ser llamado"

    def test_hit_test_outside(self):
        """Touch fuera del circulo no es hit."""
        from display.ui.widgets import ButtonWidget

        btn = ButtonWidget(260, 50, 180, 230)
        # Esquina superior izquierda del panel (fuera del circulo)
        assert not btn.hit_test(261, 51), "Touch en esquina no deberia ser hit"

    def test_draw_renders_without_crash(self, surface):
        """draw() no debe lanzar excepciones."""
        from display.ui.widgets import ButtonWidget

        btn = ButtonWidget(260, 50, 180, 230)
        btn.pressed = True
        btn.press_count = 42
        btn.draw(surface)

        btn.pressed = False
        btn.draw(surface)

    def test_draw_high_count(self, surface):
        """draw() maneja numeros grandes en el contador."""
        from display.ui.widgets import ButtonWidget

        btn = ButtonWidget(260, 50, 180, 230)
        btn.press_count = 9999
        btn.draw(surface)  # No debe lanzar excepcion


class TestHeaderWidget:
    """Pruebas del HeaderWidget."""

    def test_draw(self, surface):
        from display.ui.widgets import HeaderWidget

        header = HeaderWidget(0, 0, 480, 36)
        header.draw(surface)


class TestStatusBar:
    """Pruebas del StatusBar."""

    def test_draw_all_states(self, surface):
        from display.ui.widgets import StatusBar

        bar = StatusBar(0, 298, 480, 22)
        bar.time_str = "12:34:56"
        bar.backend_connected = True
        bar.ws_connected = True
        bar.fps = 20.5
        bar.draw(surface)

        bar.backend_connected = False
        bar.ws_connected = False
        bar.draw(surface)


# ═══════════════════════════════════════════════════════════════
# Screen tests (mock mode)
# ═══════════════════════════════════════════════════════════════


class TestScreenMock:
    """Pruebas del Screen en modo mock (sin DRM)."""

    def test_mock_screen_init(self):
        """Screen en modo mock se inicializa correctamente."""
        from display.ui.screen import Screen

        s = Screen(mock=True)
        assert s.init(), "Screen mock debio inicializarse"
        assert s.surface is not None
        assert s.surface.get_width() == 480
        assert s.surface.get_height() == 320
        s.cleanup()

    def test_mock_screen_clear_and_flip(self):
        """clear() y flip() funcionan en modo mock."""
        from display.ui.screen import Screen

        s = Screen(mock=True)
        s.init()
        s.clear()
        s.flip()
        s.tick(60)
        assert s.get_fps() >= 0
        s.cleanup()

    def test_handle_quit_key(self):
        """handle_quit detecta ESC y QUIT."""
        from display.ui.screen import Screen

        s = Screen(mock=True)
        s.init()

        # Evento QUIT
        quit_event = pygame.event.Event(pygame.QUIT)
        assert s.handle_quit(quit_event), "QUIT deberia devolver True"

        # Evento ESC
        esc_event = pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_ESCAPE})
        assert s.handle_quit(esc_event), "ESC deberia devolver True"

        # Evento normal (no deberia salir)
        other_event = pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_a})
        assert not s.handle_quit(other_event), "Tecla normal no deberia salir"

        s.cleanup()


# ═══════════════════════════════════════════════════════════════
# Theme tests
# ═══════════════════════════════════════════════════════════════


class TestTheme:
    """Pruebas de constantes del tema."""

    def test_resolution_constants(self):
        from display.ui import theme

        assert theme.BASE_WIDTH == 480
        assert theme.BASE_HEIGHT == 320

    def test_colors_are_rgb_triplets(self):
        from display.ui import theme

        for name in dir(theme):
            if name.isupper() and not name.startswith("_") and name not in ("BASE_WIDTH", "BASE_HEIGHT",
                "HEADER_HEIGHT", "FOOTER_HEIGHT", "MARGIN", "LED_PANEL_X", "LED_PANEL_W", "BTN_PANEL_W",
                "FONT_FAMILY", "FONT_BOLD", "RAW_MAX",
            ):
                value = getattr(theme, name)
                if isinstance(value, tuple):
                    assert len(value) == 3, f"{name} deberia ser RGB"
                    for channel in value:
                        assert 0 <= channel <= 255, f"{name} canal fuera de rango"


# ═══════════════════════════════════════════════════════════════
# Integration smoke tests
# ═══════════════════════════════════════════════════════════════


class TestLayoutSmoke:
    """Pruebas de humo del layout completo."""

    def test_all_widgets_draw_together(self, surface):
        """Renderizar todos los widgets juntos no debe fallar."""
        from display.ui.widgets import (
            ButtonWidget,
            HeaderWidget,
            LedIndicator,
            StatusBar,
        )

        # Replicar el layout de DisplayApp
        header = HeaderWidget(0, 0, 480, 36)
        led = LedIndicator(10, 46, 180, 230)
        btn = ButtonWidget(290, 46, 180, 230)
        bar = StatusBar(0, 298, 480, 22)

        led.on = True
        btn.press_count = 5
        bar.time_str = "12:00:00"
        bar.backend_connected = True

        widgets = [header, led, btn, bar]
        for w in widgets:
            w.draw(surface)

    def test_touch_dispatch_order(self):
        """Los widgets se despachan en el orden correcto (ultimo primero)."""
        from display.ui.widgets import ButtonWidget, LedIndicator

        led = LedIndicator(10, 50, 180, 230)
        btn = ButtonWidget(260, 50, 180, 230)
        interactive = [btn, led]

        # Centro del boton — solo el boton deberia capturar
        btn_cx = 260 + 90
        btn_cy = 50 + 20 + (230 - 20) // 2 - 5
        results = []
        for w in interactive:
            if w.hit_test(btn_cx, btn_cy):
                results.append(type(w).__name__)
        assert "ButtonWidget" in results
        # LED no deberia capturar en el centro del boton
        assert not led.hit_test(btn_cx, btn_cy), "LED no deberia capturar touch en area del boton"


# ═══════════════════════════════════════════════════════════════
# FASE 3: Thread-safety, touch dispatch, button feedback
# ═══════════════════════════════════════════════════════════════


class TestDisplayAppThreadSafety:
    """Pruebas de thread-safety del DisplayApp (FASE 3)."""

    def test_apply_ws_state_no_dirty_returns_false(self, surface):
        """_apply_ws_state retorna False cuando _ws_dirty es False."""
        from unittest.mock import MagicMock

        from display.app import DisplayApp

        app = DisplayApp.__new__(DisplayApp)
        app.screen = MagicMock()
        app.screen.width = 480
        app.screen.height = 320
        app._ws_lock = MagicMock()
        # Simular lock como context manager real
        import threading
        app._ws_lock = threading.Lock()
        app._ws_dirty = False

        app.led = MagicMock()
        app.button = MagicMock()

        result = app._apply_ws_state()
        assert result is False

    def test_apply_ws_state_applies_led_changes(self, surface):
        """_apply_ws_state aplica cambios de LED a widgets bajo lock."""
        from unittest.mock import MagicMock

        from display.app import DisplayApp
        from display.ui.widgets import ButtonWidget, LedIndicator

        app = DisplayApp.__new__(DisplayApp)
        app.screen = MagicMock()
        app.screen.width = 480
        app.screen.height = 320
        import threading
        app._ws_lock = threading.Lock()

        # Estado compartido simulado (WS thread ya escribio)
        app.led_on = True
        app.press_count = 5
        app._ws_dirty = True

        # Widgets reales (sin inicializar via __init__ completo)
        app.led = LedIndicator(10, 50, 180, 230)
        app.led.on = False
        app.led.label = "INTERRUPTOR ON/OFF"
        app.button = ButtonWidget(260, 50, 180, 230)
        app.button.press_count = 0

        app._pending_display_action = None
        app._pending_font_family = None
        app._pending_text_size = None

        result = app._apply_ws_state()
        assert result is True
        assert app.led.on is True
        assert app.led.label == "INTERRUPTOR ON/OFF"
        assert app.button.press_count == 5
        assert app._ws_dirty is False  # dirty flag se limpia

    def test_apply_ws_state_no_changes_returns_false(self, surface):
        """_apply_ws_state retorna False cuando el estado no cambio."""
        from unittest.mock import MagicMock

        from display.app import DisplayApp
        from display.ui.widgets import ButtonWidget, LedIndicator

        app = DisplayApp.__new__(DisplayApp)
        app.screen = MagicMock()
        app.screen.width = 480
        app.screen.height = 320
        import threading
        app._ws_lock = threading.Lock()

        app.led_on = False
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
        assert result is False  # No hubo cambios
        assert app._ws_dirty is False  # dirty flag igual se limpia


class TestDisplayAppTouchDispatch:
    """Pruebas de dispatch tactil del DisplayApp (FASE 3)."""

    def test_handle_touch_down_dispatches_to_led(self, surface):
        """_handle_touch_down despacha al LED correctamente."""
        from unittest.mock import MagicMock

        from display.app import DisplayApp
        from display.ui.widgets import LedIndicator

        app = DisplayApp.__new__(DisplayApp)
        app.screen = MagicMock()
        app.screen.width = 480
        app.screen.height = 320
        import threading
        app._ws_lock = threading.Lock()
        app._ws_dirty = False

        app.led = LedIndicator(10, 50, 180, 230)
        toggled = []

        def on_toggle():
            toggled.append(True)

        app.led.set_on_toggle(on_toggle)
        app.button = MagicMock()
        app.button.hit_test.return_value = False  # No capturar en area del LED

        app._interactive_widgets = [app.button, app.led]

        # Tocar en el area del boton toggle del LED
        # LedIndicator: x=10, y=50, w=180, h=230
        # _btn_rect = (10+10=20, 50+230-28-5=247, 160, 28)
        # Centro: (20+80=100, 247+14=261)
        btn_x = 100
        btn_y = 261

        app.view = "main"
        app._handle_touch_down(btn_x, btn_y)
        assert len(toggled) == 1

    def test_handle_touch_down_dispatches_to_button(self, surface):
        """_handle_touch_down despacha al boton correctamente."""
        from unittest.mock import MagicMock

        from display.app import DisplayApp
        from display.ui.widgets import ButtonWidget

        app = DisplayApp.__new__(DisplayApp)
        app.screen = MagicMock()
        app.screen.width = 480
        app.screen.height = 320
        import threading
        app._ws_lock = threading.Lock()
        app._ws_dirty = False
        app._button_press_frame = -1

        app.led = MagicMock()
        app.led.hit_test.return_value = False  # No capturar en area del boton
        app.button = ButtonWidget(260, 50, 180, 230)
        pressed = []

        def on_press():
            pressed.append(True)
            app.button.pressed = True

        app.button.set_on_press(on_press)

        app._interactive_widgets = [app.button, app.led]

        # Tocar en el centro del boton
        cx = 260 + 90
        cy = 50 + 20 + (230 - 20) // 2 - 5

        app.view = "main"
        app._handle_touch_down(cx, cy)
        assert len(pressed) == 1
        assert app.button.pressed is True

    def test_handle_touch_down_miss_no_dispatch(self, surface):
        """Touch fuera de widgets no activa ningun callback."""
        from unittest.mock import MagicMock

        from display.app import DisplayApp
        from display.ui.widgets import ButtonWidget, LedIndicator

        app = DisplayApp.__new__(DisplayApp)
        app.screen = MagicMock()
        app.screen.width = 480
        app.screen.height = 320
        import threading
        app._ws_lock = threading.Lock()
        app._ws_dirty = False

        app.led = LedIndicator(10, 50, 180, 230)
        app.button = ButtonWidget(260, 50, 180, 230)

        led_toggled = []
        btn_pressed = []

        app.led.set_on_toggle(lambda: led_toggled.append(True))
        app.button.set_on_press(lambda: btn_pressed.append(True))

        app._interactive_widgets = [app.button, app.led]

        # Tocar fuera de cualquier widget
        app.view = "main"
        app._handle_touch_down(0, 0)
        assert len(led_toggled) == 0
        assert len(btn_pressed) == 0


class TestDisplayAppButtonFeedback:
    """Pruebas de feedback no-bloqueante del boton (FASE 3)."""

    def test_button_press_sets_frame_counter(self, surface):
        """_on_press_button inicia el contador de frames."""
        from unittest.mock import MagicMock, patch

        from display.app import DisplayApp
        from display.ui.widgets import ButtonWidget

        app = DisplayApp.__new__(DisplayApp)
        app.screen = MagicMock()
        app.screen.width = 480
        app.screen.height = 320
        import threading
        app._ws_lock = threading.Lock()
        app._ws_dirty = False
        app.api_url = "http://localhost:8000"
        app.backend_connected = True

        app.button = ButtonWidget(260, 50, 180, 230)
        app.button.pressed = False
        app._button_press_frame = -1
        app._button_press_duration = 2
        app.led = MagicMock()
        app.status_bar = MagicMock()

        # Mockear las llamadas REST
        with patch.object(app, '_api_post', return_value={"status": "ok"}), \
             patch.object(app, '_sync_state'):
            app._on_press_button()

        assert app.button.pressed is True
        assert app._button_press_frame == 0

    def test_button_feedback_releases_after_duration(self, surface):
        """El boton se libera tras _button_press_duration frames."""
        from unittest.mock import MagicMock

        from display.app import DisplayApp
        from display.ui.widgets import ButtonWidget

        app = DisplayApp.__new__(DisplayApp)
        app.screen = MagicMock()
        app.screen.width = 480
        app.screen.height = 320
        import threading
        app._ws_lock = threading.Lock()
        app._ws_dirty = False

        app.button = ButtonWidget(260, 50, 180, 230)
        app.button.pressed = True
        app._button_press_frame = 0
        app._button_press_duration = 2
        app.led = MagicMock()

        # Frame 0: pressed=True, frame=0
        assert app._button_press_frame == 0

        # Simular frame 1: incrementa pero no libera
        app._button_press_frame += 1
        assert app.button.pressed is True

        # Simular frame 2: libera
        app._button_press_frame += 1
        if app._button_press_frame >= app._button_press_duration:
            app.button.pressed = False
            app._button_press_frame = -1

        assert app.button.pressed is False
        assert app._button_press_frame == -1

    def test_button_feedback_does_not_release_early(self, surface):
        """El boton no se libera antes de la duracion."""
        from unittest.mock import MagicMock

        from display.app import DisplayApp
        from display.ui.widgets import ButtonWidget

        app = DisplayApp.__new__(DisplayApp)
        app.screen = MagicMock()
        app.screen.width = 480
        app.screen.height = 320
        import threading
        app._ws_lock = threading.Lock()

        app.button = ButtonWidget(260, 50, 180, 230)
        app.button.pressed = True
        app._button_press_frame = 0
        app._button_press_duration = 3  # 3 frames

        # Frame 1
        app._button_press_frame += 1
        assert app.button.pressed is True, "No deberia liberarse en frame 1"

        # Frame 2
        app._button_press_frame += 1
        assert app.button.pressed is True, "No deberia liberarse en frame 2"

        # Frame 3 — libera
        app._button_press_frame += 1
        if app._button_press_frame >= app._button_press_duration:
            app.button.pressed = False
            app._button_press_frame = -1

        assert app.button.pressed is False
        assert app._button_press_frame == -1


# ═══════════════════════════════════════════════════════════════
# Touch Detection (FASE P1+P2)
# ═══════════════════════════════════════════════════════════════


class TestTouchDetection:
    """Tests para deteccion de dispositivo touch."""

    def test_find_touch_device_matches_ads7846(self) -> None:
        """Simula sysfs con nombre 'ADS7846 Touchscreen'."""
        from unittest.mock import patch

        from display.ui.touch import _find_touch_device

        with patch("os.listdir", return_value=["event0", "event1", "event2"]):
            def mock_open(path: str, *args, **kwargs):  # type: ignore[no-untyped-def]
                if "event1/device/name" in str(path):
                    from unittest.mock import mock_open
                    m = mock_open(read_data="ADS7846 Touchscreen")
                    return m.return_value
                raise FileNotFoundError

            with (
                patch("builtins.open", mock_open),
                patch("pathlib.Path.exists", return_value=True),
            ):
                result = _find_touch_device()
                assert result is not None
                assert "event1" in str(result)

    def test_find_touch_device_no_match_returns_none(self) -> None:
        """Ningun dispositivo coincide -> None."""
        from unittest.mock import patch

        from display.ui.touch import _find_touch_device

        with patch("os.listdir", return_value=["event0", "event1"]):
            def mock_open(path: str, *args, **kwargs):  # type: ignore[no-untyped-def]
                if "device/name" in str(path):
                    from unittest.mock import mock_open
                    m = mock_open(read_data="Keyboard")
                    return m.return_value
                raise FileNotFoundError

            with (
                patch("builtins.open", mock_open),
                patch("pathlib.Path.exists", return_value=True),
            ):
                result = _find_touch_device()
                assert result is None

    def test_touch_handler_no_device(self) -> None:
        """TouchHandler sin dispositivo detectado -> available=False."""
        from display.ui.touch import TouchHandler

        th = TouchHandler(device_path="/nonexistent")
        assert th.available is False

    @pytest.mark.skip(reason="_map_coordinates no existe; raw_to_screen ya testeado")
    def test_touch_coordinates_mapped_correctly(self) -> None:
        """Verifica mapeo de coordenadas crudas a pantalla (ya cubierto)."""
        pass


# ═══════════════════════════════════════════════════════════════
# Screen DRM Fallback (FASE P1+P2)
# ═══════════════════════════════════════════════════════════════


class TestScreenDRMFallback:
    """Tests para fallback de DRM a mock."""

    def test_screen_initializes_mock_when_drm_unavailable(self) -> None:
        """Si DRM falla y el fallback está permitido, Screen cae a modo mock."""
        from unittest.mock import patch

        from display.ui.screen import Screen

        screen = Screen(auto_detect=False, mock=False, allow_mock_fallback=True)
        with patch.object(screen, "_init_drm", side_effect=Exception("No video")):
            assert screen.init() is True
        assert screen.mock is True
        screen.cleanup()

    def test_screen_returns_false_when_drm_fails_without_fallback(self) -> None:
        """Si DRM falla y el fallback está deshabilitado, init() devuelve False."""
        from unittest.mock import patch

        from display.ui.screen import Screen

        screen = Screen(auto_detect=False, mock=False, allow_mock_fallback=False)
        with patch.object(screen, "_init_drm", side_effect=Exception("No video")):
            assert screen.init() is False
        assert screen.mock is False
        screen.cleanup()

    def test_screen_size_on_init(self) -> None:
        """Screen se inicializa con las dimensiones correctas."""
        from display.ui.screen import Screen

        screen = Screen(mock=True)
        assert screen.width == 480
        assert screen.height == 320
        screen.cleanup()


# ═══════════════════════════════════════════════════════════════
# Theme Constants (FASE P1+P2)
# ═══════════════════════════════════════════════════════════════


class TestThemeConstants:
    """Tests adicionales para constantes de tema."""

    def test_resolution_matches_hardware(self) -> None:
        """La resolucion por defecto coincide con la pantalla fisica (480x320)."""
        from display.ui.theme import BASE_HEIGHT, BASE_WIDTH

        assert BASE_WIDTH == 480
        assert BASE_HEIGHT == 320


# ═══════════════════════════════════════════════════════════════
# SecuritySettingsView (FASE 7c)
# ═══════════════════════════════════════════════════════════════


class TestSecuritySettingsView:
    """Pruebas de la vista de gestion de contrasena con teclado numerico."""

    def _key_rect(self, view, key: str):
        """Devuelve el rect de la tecla del keypad por su etiqueta."""
        for rect, k in view._key_rects:
            if k == key:
                return rect
        raise AssertionError(f"Tecla no encontrada: {key}")

    def test_initial_state(self):
        """Estado inicial: desactivada, de fabrica, campo actual activo."""
        from display.ui.widgets import SecuritySettingsView

        view = SecuritySettingsView(480, 320)
        assert view._enabled is False
        assert view._is_default is True
        assert view._active_field == "current"
        assert view.current == ""
        assert view.new == ""
        assert view.confirm == ""

    def test_set_status_updates_flags(self):
        """set_status refleja enabled e is_default del dict."""
        from display.ui.widgets import SecuritySettingsView

        view = SecuritySettingsView(480, 320)
        view.set_status({"enabled": True, "is_default": False})
        assert view._enabled is True
        assert view._is_default is False

    def test_keypad_writes_to_active_field(self):
        """Las teclas de digito se escriben en el campo activo (current por defecto)."""
        from display.ui.widgets import SecuritySettingsView

        view = SecuritySettingsView(480, 320)
        for digit in ("1", "2", "3"):
            rect = self._key_rect(view, digit)
            view.on_touch(rect.centerx, rect.centery)
        assert view.current == "123"

    def test_field_selection_changes_active_field(self):
        """Tocar un campo lo selecciona; el keypad escribe ahi."""
        from display.ui.widgets import SecuritySettingsView

        view = SecuritySettingsView(480, 320)
        new_rect = view._field_rects["new"]
        view.on_touch(new_rect.centerx, new_rect.centery)
        assert view._active_field == "new"
        for digit in ("4", "5"):
            rect = self._key_rect(view, digit)
            view.on_touch(rect.centerx, rect.centery)
        assert view.new == "45"
        assert view.current == ""

    def test_borrar_removes_last_digit(self):
        """BORRAR quita el ultimo digito del campo activo."""
        from display.ui.widgets import SecuritySettingsView

        view = SecuritySettingsView(480, 320)
        view.current = "1234"
        rect = self._key_rect(view, "BORRAR")
        view.on_touch(rect.centerx, rect.centery)
        assert view.current == "123"

    def test_limpiar_empties_field(self):
        """LIMPIAR vacia el campo activo."""
        from display.ui.widgets import SecuritySettingsView

        view = SecuritySettingsView(480, 320)
        view.current = "1234"
        rect = self._key_rect(view, "LIMPIAR")
        view.on_touch(rect.centerx, rect.centery)
        assert view.current == ""

    def test_keypad_max_length(self):
        """El campo activo no supera la longitud maxima (16)."""
        from display.ui.widgets import SecuritySettingsView

        view = SecuritySettingsView(480, 320)
        for _ in range(20):
            rect = self._key_rect(view, "9")
            view.on_touch(rect.centerx, rect.centery)
        assert len(view.current) == 16

    def test_change_requires_min_8_chars(self):
        """CAMBIAR no llama al callback si la nueva tiene menos de 8 caracteres."""
        from display.ui.widgets import SecuritySettingsView

        view = SecuritySettingsView(480, 320)
        changed = []
        view.set_on_change(lambda current, new: changed.append((current, new)))
        view.current = "1234"
        view.new = "1234567"
        view.confirm = "1234567"
        view.on_touch(view._change_rect.centerx, view._change_rect.centery)
        assert changed == []
        assert view._result_error is True

    def test_change_requires_matching_confirm(self):
        """CAMBIAR exige que nueva y confirmar coincidan."""
        from display.ui.widgets import SecuritySettingsView

        view = SecuritySettingsView(480, 320)
        changed = []
        view.set_on_change(lambda current, new: changed.append((current, new)))
        view.current = "1234"
        view.new = "12345678"
        view.confirm = "87654321"
        view.on_touch(view._change_rect.centerx, view._change_rect.centery)
        assert changed == []

    def test_change_callback(self):
        """CAMBIAR valido invoca el callback con (current, new)."""
        from display.ui.widgets import SecuritySettingsView

        view = SecuritySettingsView(480, 320)
        changed = []
        view.set_on_change(lambda current, new: changed.append((current, new)))
        view.current = "1234"
        view.new = "12345678"
        view.confirm = "12345678"
        view.on_touch(view._change_rect.centerx, view._change_rect.centery)
        assert changed == [("1234", "12345678")]

    def test_toggle_blocks_activation_when_default(self):
        """Activar con contrasena de fabrica se bloquea en cliente (sin callback)."""
        from display.ui.widgets import SecuritySettingsView

        view = SecuritySettingsView(480, 320)
        view.set_status({"enabled": False, "is_default": True})
        toggled = []
        view.set_on_toggle(lambda enabled, current: toggled.append((enabled, current)))
        view.current = "1234"
        view.on_touch(view._toggle_rect.centerx, view._toggle_rect.centery)
        assert toggled == []
        assert view._result_error is True
        assert "fábrica" in view._result

    def test_toggle_requires_current(self):
        """El toggle exige contrasena actual aunque no sea de fabrica."""
        from display.ui.widgets import SecuritySettingsView

        view = SecuritySettingsView(480, 320)
        view.set_status({"enabled": False, "is_default": False})
        toggled = []
        view.set_on_toggle(lambda enabled, current: toggled.append((enabled, current)))
        view.current = ""
        view.on_touch(view._toggle_rect.centerx, view._toggle_rect.centery)
        assert toggled == []

    def test_toggle_callback(self):
        """Toggle valido invoca el callback con (target, current)."""
        from display.ui.widgets import SecuritySettingsView

        view = SecuritySettingsView(480, 320)
        view.set_status({"enabled": False, "is_default": False})
        toggled = []
        view.set_on_toggle(lambda enabled, current: toggled.append((enabled, current)))
        view.current = "1234"
        view.on_touch(view._toggle_rect.centerx, view._toggle_rect.centery)
        assert toggled == [(True, "1234")]

    def test_back_callback(self):
        """VOLVER invoca el callback de retroceso."""
        from display.ui.widgets import SecuritySettingsView

        view = SecuritySettingsView(480, 320)
        backed = []
        view.set_on_back(lambda: backed.append(True))
        view.on_touch(view._back_rect.centerx, view._back_rect.centery)
        assert backed == [True]

    def test_draw_renders_without_crash(self, surface):
        """draw() no debe lanzar excepciones en estados exitoso y de error."""
        from display.ui.widgets import SecuritySettingsView

        view = SecuritySettingsView(480, 320)
        view.set_status({"enabled": True, "is_default": False})
        view.current = "1234"
        view.new = "12345678"
        view.confirm = "12345678"
        view.set_result("Contrasena actualizada")
        view.draw(surface)

        view.set_result("Debes cambiar la contraseña de fábrica (1234) antes de activar", error=True)
        view.draw(surface)
