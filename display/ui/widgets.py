"""Widgets — Componentes visuales para la UI táctil en Pygame.

Jerarquia de widgets:
    Widget (abstracto)
    ├── Panel          — Contenedor rectangular con borde
    ├── HeaderWidget   — Barra de titulo superior
    ├── StatusBar      — Barra de estado inferior
    ├── LedIndicator   — Circulo LED con estado ON/OFF y boton toggle
    └── ButtonWidget   — Boton circular con contador de pulsaciones

Soporta pygame.freetype (preferido) y pygame.font (fallback para ARMv6).
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

import pygame

# ── Font module detection (freetype not always available on ARMv6) ──
_HAS_FREETYPE = hasattr(pygame, "freetype")
if _HAS_FREETYPE:
    import pygame.freetype

from display.ui.theme import (
    BACKGROUND,
    BTN_IDLE_BG,
    BTN_IDLE_MID,
    BTN_PRESSED_BG,
    BTN_PRESSED_MID,
    BTN_PRESSED_TEXT,
    BUTTON_BG,
    BUTTON_TEXT,
    FOOTER_BG,
    FOOTER_TEXT,
    FONT_BOLD,
    FONT_FAMILY,
    FONT_SIZE_COUNTER,
    FONT_SIZE_HEADING,
    FONT_SIZE_NORMAL,
    FONT_SIZE_SMALL,
    FONT_SIZE_TITLE,
    HEADER_BG,
    HEADER_TEXT,
    LED_OFF_BG,
    LED_OFF_HIGHLIGHT,
    LED_OFF_MID,
    LED_ON_CORE,
    LED_ON_GLOW,
    LED_ON_HIGHLIGHT,
    LED_ON_MID,
    PANEL_BG,
    PANEL_BORDER,
    SUCCESS,
    TEXT_DIM,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    WARNING,
)

if TYPE_CHECKING:
    pass

logger = logging.getLogger("rpi_hmi.display.widgets")

# ── Cache de fuentes ──────────────────────────────────────────
FontType = object  # pygame.freetype.Font | pygame.font.Font
_font_cache: dict[tuple[str, int], FontType] = {}


def _get_font(name: str, size: int) -> FontType:
    """Obtiene una fuente del cache o la crea.

    Usa pygame.freetype si esta disponible, o pygame.font como fallback.
    Si ningun modulo de fuentes esta disponible, devuelve un objeto dummy.
    """
    key = (name, size)
    if key not in _font_cache:
        if _HAS_FREETYPE:
            try:
                _font_cache[key] = pygame.freetype.SysFont(name, size)
                return _font_cache[key]
            except Exception:
                pass
            try:
                _font_cache[key] = pygame.freetype.Font(None, size)
                return _font_cache[key]
            except Exception:
                pass
        else:
            if not pygame.font.get_init():
                pygame.font.init()
            try:
                _font_cache[key] = pygame.font.SysFont(name, size)
                return _font_cache[key]
            except Exception:
                pass
            try:
                _font_cache[key] = pygame.font.Font(None, size)
                return _font_cache[key]
            except Exception:
                pass
        # Dummy: devolver None (las funciones _render_text / _get_text_rect lo manejan)
        _font_cache[key] = None
    return _font_cache[key]


def _render_text(surface: pygame.Surface, font: FontType, text: str,
                 color: tuple[int, int, int], x: int, y: int) -> pygame.Rect:
    """Renderiza texto en la superficie. Compatible con freetype y font."""
    if font is None:
        return pygame.Rect(x, y, 0, 0)
    if _HAS_FREETYPE:
        rect = font.render_to(surface, (x, y), text, color)
        if rect is None:
            return pygame.Rect(x, y, 0, 0)
        return pygame.Rect(rect)
    else:
        text_surf = font.render(text, True, color)
        surface.blit(text_surf, (x, y))
        return text_surf.get_rect(x=x, y=y)


def _get_text_rect(font: FontType, text: str) -> pygame.Rect:
    """Obtiene el rectangulo que ocuparia el texto."""
    if font is None:
        return pygame.Rect(0, 0, 0, 0)
    if _HAS_FREETYPE:
        raw = font.get_rect(text)
        if raw is None:
            return pygame.Rect(0, 0, 0, 0)
        return pygame.Rect(raw)
    else:
        text_surf = font.render(text, True, (0, 0, 0))
        return text_surf.get_rect()


# ═══════════════════════════════════════════════════════════════
# Clase base
# ═══════════════════════════════════════════════════════════════


class Widget(ABC):
    """Componente visual base con bounding box y manejador de eventos."""

    def __init__(self, x: int, y: int, w: int, h: int) -> None:
        self.rect = pygame.Rect(x, y, w, h)
        self.visible: bool = True
        self.enabled: bool = True

    @abstractmethod
    def draw(self, surface: pygame.Surface) -> None:
        ...

    def hit_test(self, screen_x: int, screen_y: int) -> bool:
        return self.visible and self.enabled and self.rect.collidepoint(screen_x, screen_y)

    def on_touch(self, screen_x: int, screen_y: int) -> bool:
        return False


# ═══════════════════════════════════════════════════════════════
# Panel (contenedor generico)
# ═══════════════════════════════════════════════════════════════


class Panel(Widget):
    """Panel rectangular con fondo y borde."""

    def __init__(
        self, x: int, y: int, w: int, h: int,
        bg_color: tuple[int, int, int] = PANEL_BG,
        border_color: tuple[int, int, int] = PANEL_BORDER,
        border_width: int = 2,
    ) -> None:
        super().__init__(x, y, w, h)
        self.bg_color = bg_color
        self.border_color = border_color
        self.border_width = border_width

    def draw(self, surface: pygame.Surface) -> None:
        if not self.visible:
            return
        pygame.draw.rect(surface, self.bg_color, self.rect)
        if self.border_width > 0:
            pygame.draw.rect(surface, self.border_color, self.rect, self.border_width)


# ═══════════════════════════════════════════════════════════════
# Header
# ═══════════════════════════════════════════════════════════════


class HeaderWidget(Widget):
    """Barra de titulo superior con nombre de la app y version."""

    def __init__(self, x: int, y: int, w: int, h: int,
                 title: str = "RASPBERRY HMI", version: str = "v2.0") -> None:
        super().__init__(x, y, w, h)
        self.title = title
        self.version = version

    def draw(self, surface: pygame.Surface) -> None:
        if not self.visible:
            return

        pygame.draw.rect(surface, HEADER_BG, self.rect)

        title_font = _get_font(FONT_BOLD, FONT_SIZE_TITLE)
        ver_font = _get_font(FONT_FAMILY, FONT_SIZE_SMALL)

        title_rect = _get_text_rect(title_font, self.title)
        title_y = self.rect.y + (self.rect.height - title_rect.height) // 2
        _render_text(surface, title_font, self.title, HEADER_TEXT, self.rect.x + 10, title_y)

        ver_rect = _get_text_rect(ver_font, self.version)
        ver_y = self.rect.y + (self.rect.height - ver_rect.height) // 2
        ver_x = self.rect.x + self.rect.width - ver_rect.width - 10
        _render_text(surface, ver_font, self.version, TEXT_DIM, ver_x, ver_y)


# ═══════════════════════════════════════════════════════════════
# StatusBar
# ═══════════════════════════════════════════════════════════════


class StatusBar(Widget):
    """Barra de estado inferior con hora y estado de conexion."""

    def __init__(self, x: int, y: int, w: int, h: int) -> None:
        super().__init__(x, y, w, h)
        self.time_str: str = "--:--:--"
        self.backend_connected: bool = False
        self.ws_connected: bool = False
        self.fps: float = 0.0

    def draw(self, surface: pygame.Surface) -> None:
        if not self.visible:
            return

        pygame.draw.rect(surface, FOOTER_BG, self.rect)

        font = _get_font(FONT_FAMILY, FONT_SIZE_SMALL)
        font_y = self.rect.y + (self.rect.height - FONT_SIZE_SMALL) // 2

        # Hora (izquierda)
        _render_text(surface, font, self.time_str, FOOTER_TEXT, self.rect.x + 10, font_y)

        # FPS (centro)
        fps_text = f"FPS:{self.fps:.0f}"
        fps_rect = _get_text_rect(font, fps_text)
        fps_x = self.rect.x + (self.rect.width - fps_rect.width) // 2
        _render_text(surface, font, fps_text, FOOTER_TEXT, fps_x, font_y)

        # Estado backend (derecha)
        status = "API:OK" if self.backend_connected else "API:--"
        color = SUCCESS if self.backend_connected else WARNING
        status_rect = _get_text_rect(font, status)
        status_x = self.rect.x + self.rect.width - status_rect.width - 10
        _render_text(surface, font, status, color, status_x, font_y)


# ═══════════════════════════════════════════════════════════════
# LedIndicator — Circulo LED con boton toggle
# ═══════════════════════════════════════════════════════════════


class LedIndicator(Widget):
    """Indicador LED circular con boton TOGGLE integrado."""

    def __init__(self, x: int, y: int, w: int, h: int,
                 label: str = "LED 1", gpio_pin: int = 17) -> None:
        super().__init__(x, y, w, h)
        self.on: bool = False
        self.label = label
        self.gpio_pin = gpio_pin
        self._on_toggle: callable | None = None

        padding = 10
        title_h = 20
        btn_h = 28
        margin_btn = 5

        self._title_rect = pygame.Rect(x + padding, y + padding, w - 2 * padding, title_h)
        self._led_center_x = x + w // 2
        self._led_center_y = y + title_h + (h - title_h - btn_h - margin_btn * 2) // 2
        self._led_radius = min(w, h - title_h - btn_h) // 4
        self._btn_rect = pygame.Rect(x + padding, y + h - btn_h - margin_btn,
                                     w - 2 * padding, btn_h)

    def set_on_toggle(self, callback: callable) -> None:
        self._on_toggle = callback

    def draw(self, surface: pygame.Surface) -> None:
        if not self.visible:
            return

        pygame.draw.rect(surface, PANEL_BG, self.rect)
        pygame.draw.rect(surface, PANEL_BORDER, self.rect, 2)

        title_font = _get_font(FONT_FAMILY, FONT_SIZE_NORMAL)
        title_rect = _get_text_rect(title_font, self.label)
        title_x = self.rect.x + (self.rect.width - title_rect.width) // 2
        _render_text(surface, title_font, self.label, TEXT_SECONDARY, title_x, self._title_rect.y)

        self._draw_led(surface)
        self._draw_toggle_button(surface)

    def _draw_led(self, surface: pygame.Surface) -> None:
        cx, cy = self._led_center_x, self._led_center_y
        r = self._led_radius

        if self.on:
            pygame.draw.circle(surface, LED_ON_GLOW, (cx, cy), r + 6)
            pygame.draw.circle(surface, LED_ON_MID, (cx, cy), r + 2)
            pygame.draw.circle(surface, LED_ON_CORE, (cx, cy), r)
            pygame.draw.circle(surface, LED_ON_HIGHLIGHT, (cx, cy), r - 3)
            pygame.draw.circle(surface, (255, 200, 180), (cx - r // 3, cy - r // 3), r // 5)
            state_font = _get_font(FONT_BOLD, FONT_SIZE_NORMAL)
            state_text = "ENCENDIDO"
            state_color = LED_ON_CORE
        else:
            pygame.draw.circle(surface, LED_OFF_BG, (cx, cy), r)
            pygame.draw.circle(surface, LED_OFF_MID, (cx, cy), r - 2)
            pygame.draw.circle(surface, LED_OFF_HIGHLIGHT, (cx - r // 3, cy - r // 3), r // 5)
            state_font = _get_font(FONT_FAMILY, FONT_SIZE_NORMAL)
            state_text = "APAGADO"
            state_color = TEXT_DIM

        state_rect = _get_text_rect(state_font, state_text)
        state_x = cx - state_rect.width // 2
        state_y = cy + r + 6
        _render_text(surface, state_font, state_text, state_color, state_x, state_y)

    def _draw_toggle_button(self, surface: pygame.Surface) -> None:
        label = "APAGAR" if self.on else "ENCENDER"
        btn_rect = self._btn_rect

        pygame.draw.rect(surface, BUTTON_BG, btn_rect)
        pygame.draw.rect(surface, TEXT_DIM, btn_rect, 1)

        btn_font = _get_font(FONT_BOLD, FONT_SIZE_NORMAL)
        text_rect = _get_text_rect(btn_font, label)
        text_x = btn_rect.x + (btn_rect.width - text_rect.width) // 2
        text_y = btn_rect.y + (btn_rect.height - text_rect.height) // 2
        _render_text(surface, btn_font, label, BUTTON_TEXT, text_x, text_y)

    def hit_test(self, screen_x: int, screen_y: int) -> bool:
        if not self.visible or not self.enabled:
            return False
        return self._btn_rect.collidepoint(screen_x, screen_y)

    def on_touch(self, screen_x: int, screen_y: int) -> bool:
        if self._btn_rect.collidepoint(screen_x, screen_y):
            if self._on_toggle:
                self._on_toggle()
            return True
        return False


# ═══════════════════════════════════════════════════════════════
# ButtonWidget — Boton circular con contador de pulsaciones
# ═══════════════════════════════════════════════════════════════


class ButtonWidget(Widget):
    """Boton circular interactivo con contador de pulsaciones."""

    def __init__(self, x: int, y: int, w: int, h: int,
                 label: str = "BOTON") -> None:
        super().__init__(x, y, w, h)
        self.pressed: bool = False
        self.press_count: int = 0
        self.label = label
        self._on_press: callable | None = None

        padding = 10
        title_h = 20

        self._title_rect = pygame.Rect(x + padding, y + padding, w - 2 * padding, title_h)
        self._btn_center_x = x + w // 2
        self._btn_center_y = y + title_h + (h - title_h) // 2 - 5
        self._btn_radius = min(w, h - title_h) // 4 + 5
        self._counter_y = self._btn_center_y + self._btn_radius + 12

    def set_on_press(self, callback: callable) -> None:
        self._on_press = callback

    def draw(self, surface: pygame.Surface) -> None:
        if not self.visible:
            return

        pygame.draw.rect(surface, PANEL_BG, self.rect)
        pygame.draw.rect(surface, PANEL_BORDER, self.rect, 2)

        title_font = _get_font(FONT_FAMILY, FONT_SIZE_NORMAL)
        title_rect = _get_text_rect(title_font, self.label)
        title_x = self.rect.x + (self.rect.width - title_rect.width) // 2
        _render_text(surface, title_font, self.label, TEXT_SECONDARY, title_x, self._title_rect.y)

        self._draw_button(surface)
        self._draw_counter(surface)

    def _draw_button(self, surface: pygame.Surface) -> None:
        cx, cy = self._btn_center_x, self._btn_center_y
        r = self._btn_radius

        if self.pressed:
            pygame.draw.circle(surface, BTN_PRESSED_BG, (cx, cy), r)
            pygame.draw.circle(surface, BTN_PRESSED_MID, (cx, cy), r - 3)
            btn_font = _get_font(FONT_BOLD, FONT_SIZE_HEADING)
            label = "PULSADO"
            color = BTN_PRESSED_TEXT
        else:
            pygame.draw.circle(surface, BTN_IDLE_BG, (cx, cy), r)
            pygame.draw.circle(surface, BTN_IDLE_MID, (cx, cy), r - 3)
            btn_font = _get_font(FONT_BOLD, FONT_SIZE_HEADING)
            label = "PULSAR"
            color = BUTTON_TEXT

        text_rect = _get_text_rect(btn_font, label)
        text_x = cx - text_rect.width // 2
        text_y = cy - text_rect.height // 2
        _render_text(surface, btn_font, label, color, text_x, text_y)

    def _draw_counter(self, surface: pygame.Surface) -> None:
        label_font = _get_font(FONT_FAMILY, FONT_SIZE_SMALL)
        label_text = "Pulsaciones:"
        label_rect = _get_text_rect(label_font, label_text)
        label_x = self._btn_center_x - label_rect.width // 2
        _render_text(surface, label_font, label_text, TEXT_SECONDARY, label_x, self._counter_y)

        counter_font = _get_font(FONT_BOLD, FONT_SIZE_COUNTER)
        count_text = str(self.press_count)
        count_rect = _get_text_rect(counter_font, count_text)
        count_x = self._btn_center_x - count_rect.width // 2
        count_y = self._counter_y + label_rect.height + 4
        _render_text(surface, counter_font, count_text, HEADER_TEXT, count_x, count_y)

    def hit_test(self, screen_x: int, screen_y: int) -> bool:
        if not self.visible or not self.enabled:
            return False
        cx, cy = self._btn_center_x, self._btn_center_y
        r = self._btn_radius
        dx = screen_x - cx
        dy = screen_y - cy
        return (dx * dx + dy * dy) <= (r * r)

    def on_touch(self, screen_x: int, screen_y: int) -> bool:
        if self.hit_test(screen_x, screen_y):
            if self._on_press:
                self._on_press()
            return True
        return False
