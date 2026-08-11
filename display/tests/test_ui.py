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

        sx, sy = handler.raw_to_screen(raw_x, raw_y)
        assert sx == expected_x, f"raw=({raw_x},{raw_y}) → screen=({sx},{sy}), expected x={expected_x}"
        assert sy == expected_y, f"raw=({raw_x},{raw_y}) → screen=({sx},{sy}), expected y={expected_y}"

    def test_mapping_with_invert(self):
        """Verifica el mapeo con ejes invertidos."""
        from display.ui.touch import TouchHandler

        handler = TouchHandler.__new__(TouchHandler)
        handler.screen_width = 480
        handler.screen_height = 320
        handler.touch_max_x = 4096
        handler.touch_max_y = 4096
        handler.invert_x = True
        handler.invert_y = True

        # (0, 0) con ambos invertidos → deberia mapear a esquina opuesta
        sx, sy = handler.raw_to_screen(0, 0)
        # Sin invert: (0, 319), con invert_x: (479, 319), con invert_y: (479, 0)
        assert sx == 479
        assert sy == 0


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
