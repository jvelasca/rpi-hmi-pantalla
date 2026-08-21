"""Widgets — Componentes visuales para la UI táctil en Pygame.

Jerarquia de widgets:
    Widget (abstracto)
    ├── Panel          — Contenedor rectangular con borde
    ├── HeaderWidget   — Barra de titulo superior
    ├── StatusBar      — Barra de estado inferior
    ├── LedIndicator   — Circulo LED con estado ON/OFF e interruptor
    └── ButtonWidget   — Boton circular con contador de pulsaciones

Soporta pygame.freetype (preferido) y pygame.font (fallback para ARMv6).
"""

from __future__ import annotations

import contextlib
import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

import pygame

from display.ui.theme import (
    BTN_IDLE_BG,
    BTN_IDLE_MID,
    BTN_PRESSED_BG,
    BTN_PRESSED_MID,
    BTN_PRESSED_TEXT,
    BUTTON_BG,
    BUTTON_TEXT,
    CALIB_BG,
    CALIB_TEXT,
    CONFIG_BTN_BG,
    CONFIG_BTN_HOVER,
    CONFIG_BTN_ICON,
    ERROR,
    FONT_BOLD,
    FONT_FAMILY,
    FONT_SIZE_BIG,
    FONT_SIZE_COUNTER,
    FONT_SIZE_HEADING,
    FONT_SIZE_NORMAL,
    FONT_SIZE_SMALL,
    FONT_SIZE_TITLE,
    FOOTER_BG,
    FOOTER_TEXT,
    HEADER_BG,
    HEADER_TEXT,
    LED2_ON_CORE,
    LED2_ON_GLOW,
    LED2_ON_HIGHLIGHT,
    LED2_ON_MID,
    LED_OFF_BG,
    LED_OFF_HIGHLIGHT,
    LED_OFF_MID,
    LED_ON_CORE,
    LED_ON_GLOW,
    LED_ON_HIGHLIGHT,
    LED_ON_MID,
    NETWORK_ACCENT,
    NETWORK_ACTIVE,
    NETWORK_BG,
    NETWORK_DIM,
    NETWORK_FIELD_BG,
    NETWORK_FIELD_BORDER,
    NETWORK_STEP_BG,
    NETWORK_TEXT,
    OPTION_BG,
    OPTION_ICON_BACK,
    OPTION_ICON_FONT,
    OPTION_ICON_LOCK,
    OPTION_ICON_MONITOR,
    OPTION_ICON_NETWORK,
    OPTION_ICON_TOUCH,
    OVERLAY_BG,
    OVERLAY_BORDER,
    OVERLAY_TITLE,
    PANEL_BG,
    PANEL_BORDER,
    SUCCESS,
    TARGET_ACTIVE,
    TARGET_CENTER,
    TARGET_RING,
    TARGET_TOUCHED,
    TEST_BAR_B,
    TEST_BAR_BK,
    TEST_BAR_C,
    TEST_BAR_G,
    TEST_BAR_M,
    TEST_BAR_R,
    TEST_BAR_W,
    TEST_BAR_Y,
    TEXT_DIM,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    WARNING,
    get_font_paths,
    get_font_scale,
    set_font_settings,
)

# ── Font module detection (freetype not always available on ARMv6) ──
_HAS_FREETYPE = hasattr(pygame, "freetype")
if _HAS_FREETYPE:
    import pygame.freetype

if TYPE_CHECKING:
    pass

logger = logging.getLogger("rpi_hmi.display.widgets")

# ── Cache de fuentes ──────────────────────────────────────────
FontType = object  # pygame.freetype.Font | pygame.font.Font
_font_cache: dict[tuple[str, str, int], FontType] = {}


def clear_font_cache() -> None:
    """Vacia el cache de fuentes (llamar tras cambiar fuente/tamano)."""
    _font_cache.clear()


def apply_font_settings(font_family: str, text_size: str) -> None:
    """Aplica nuevos ajustes de fuente y limpia el cache.

    Args:
        font_family: 'dejavu' | 'liberation'.
        text_size: 'small' | 'medium' | 'large'.
    """
    set_font_settings(font_family, text_size)
    clear_font_cache()


def _get_font(name: str, size: int) -> FontType:
    """Obtiene una fuente del cache o la crea.

    Prefiere cargar el TTF directamente por ruta (nitido), evita
    pygame.freetype.SysFont porque ejecuta fc-list y puede agotar el
    timeout en Raspberry Pi, cayendo a una fuente bitmap de baja calidad.

    La familia y el tamano se resuelven en funcion de los ajustes activos
    (configurables desde el panel de configuracion / web).
    """
    bold = "bold" in name.lower()
    scaled_size = max(6, int(round(size * get_font_scale())))
    key = (name, "bold" if bold else "regular", scaled_size)
    if key not in _font_cache:
        paths = get_font_paths(bold)
        if _HAS_FREETYPE:
            # 1) Ruta directa al TTF (recomendado)
            for path in paths:
                try:
                    _font_cache[key] = pygame.freetype.Font(path, scaled_size)
                    return _font_cache[key]
                except Exception:
                    pass
            # 2) SysFont (ejecuta fc-list, puede fallar en Pi)
            try:
                _font_cache[key] = pygame.freetype.SysFont(name, scaled_size)
                return _font_cache[key]
            except Exception:
                pass
            # 3) Fuente por defecto de pygame (bitmap)
            try:
                _font_cache[key] = pygame.freetype.Font(None, scaled_size)
                return _font_cache[key]
            except Exception:
                pass
        else:
            if not pygame.font.get_init():
                pygame.font.init()
            # Cargar TTF directamente por ruta (nitido), evita SysFont/match_font
            for path in paths:
                try:
                    _font_cache[key] = pygame.font.Font(path, scaled_size)
                    return _font_cache[key]
                except Exception:
                    pass
            # Fallback: fuente por defecto de pygame (mejor que bitmap)
            try:
                _font_cache[key] = pygame.font.Font(None, scaled_size)
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
        """Dibuja el widget sobre la superficie dada (obligatorio en subclases)."""
        ...

    def hit_test(self, screen_x: int, screen_y: int) -> bool:
        """Devuelve True si el punto (screen_x, screen_y) cae dentro del widget.

        Solo responde si el widget esta visible y habilitado.
        """
        return self.visible and self.enabled and self.rect.collidepoint(screen_x, screen_y)

    def on_touch(self, screen_x: int, screen_y: int) -> bool:
        """Maneja un toque; devuelve True si el evento fue consumido.

        Por defecto no consume eventos. Las subclases interactivas lo sobreescriben.
        """
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
        """Dibuja el panel (fondo y borde) sobre la superficie."""
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
        """Dibuja la barra de titulo con el nombre de la app y la version."""
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
        """Dibuja la barra de estado (hora, FPS y estado del backend)."""
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
# LedIndicator — Circulo LED con interruptor
# ═══════════════════════════════════════════════════════════════


class LedIndicator(Widget):
    """Indicador LED circular con interruptor ON/OFF integrado."""

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
        """Registra el callback invocado al tocar el interruptor del LED."""
        self._on_toggle = callback

    def draw(self, surface: pygame.Surface) -> None:
        """Dibuja el panel LED: titulo, circulo indicador e interruptor."""
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
        """Dibuja el circulo LED con su estado (encendido/apagado)."""
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
        """Dibuja el interruptor con la etiqueta segun el estado del LED."""
        label = "ON" if self.on else "OFF"
        btn_rect = self._btn_rect

        pygame.draw.rect(surface, BUTTON_BG, btn_rect)
        pygame.draw.rect(surface, TEXT_DIM, btn_rect, 1)

        btn_font = _get_font(FONT_BOLD, FONT_SIZE_NORMAL)
        text_rect = _get_text_rect(btn_font, label)
        text_x = btn_rect.x + (btn_rect.width - text_rect.width) // 2
        text_y = btn_rect.y + (btn_rect.height - text_rect.height) // 2
        _render_text(surface, btn_font, label, BUTTON_TEXT, text_x, text_y)

    def hit_test(self, screen_x: int, screen_y: int) -> bool:
        """Devuelve True si el toque cae dentro del interruptor del LED."""
        if not self.visible or not self.enabled:
            return False
        return self._btn_rect.collidepoint(screen_x, screen_y)

    def on_touch(self, screen_x: int, screen_y: int) -> bool:
        """Activa el callback del interruptor si el toque cae en el boton."""
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
                 label: str = "PULSADOR") -> None:
        super().__init__(x, y, w, h)
        self.pressed: bool = False
        self.press_count: int = 0
        self.label = label
        self._on_press: callable | None = None
        self._on_release: callable | None = None

        padding = 10
        title_h = 20

        self._title_rect = pygame.Rect(x + padding, y + padding, w - 2 * padding, title_h)
        self._btn_center_x = x + w // 2
        self._btn_center_y = y + title_h + (h - title_h) // 2 - 5
        self._btn_radius = min(w, h - title_h) // 4 + 5
        self._counter_y = self._btn_center_y + self._btn_radius + 12

        # LED 2 (verde) — indica estado del boton PULSAR
        self._led2_center = (x + w - 20, y + title_h // 2 + padding)
        self._led2_radius = 8

    def set_on_press(self, callback: callable) -> None:
        """Registra el callback invocado al presionar el boton."""
        self._on_press = callback

    def set_on_release(self, callback: callable) -> None:
        """Registra el callback invocado al soltar el boton."""
        self._on_release = callback

    def draw(self, surface: pygame.Surface) -> None:
        """Dibuja el boton: titulo, LED 2, boton circular y contador."""
        if not self.visible:
            return

        pygame.draw.rect(surface, PANEL_BG, self.rect)
        pygame.draw.rect(surface, PANEL_BORDER, self.rect, 2)

        title_font = _get_font(FONT_FAMILY, FONT_SIZE_NORMAL)
        title_rect = _get_text_rect(title_font, self.label)
        title_x = self.rect.x + (self.rect.width - title_rect.width) // 2
        _render_text(surface, title_font, self.label, TEXT_SECONDARY, title_x, self._title_rect.y)

        self._draw_led2(surface)
        self._draw_button(surface)
        self._draw_counter(surface)

    def _draw_led2(self, surface: pygame.Surface) -> None:
        """Dibuja el LED 2 (verde) que refleja el estado del boton."""
        cx, cy = self._led2_center
        r = self._led2_radius
        if self.pressed:
            pygame.draw.circle(surface, LED2_ON_GLOW, (cx, cy), r + 4)
            pygame.draw.circle(surface, LED2_ON_MID, (cx, cy), r + 1)
            pygame.draw.circle(surface, LED2_ON_CORE, (cx, cy), r)
            pygame.draw.circle(surface, LED2_ON_HIGHLIGHT, (cx - r // 3, cy - r // 3), r // 4)
        else:
            pygame.draw.circle(surface, LED_OFF_BG, (cx, cy), r)
            pygame.draw.circle(surface, LED_OFF_MID, (cx, cy), r - 2)
            pygame.draw.circle(surface, LED_OFF_HIGHLIGHT, (cx - r // 3, cy - r // 3), r // 4)

    def _draw_button(self, surface: pygame.Surface) -> None:
        """Dibuja el circulo del boton con la etiqueta PULSAR/PULSADO."""
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
        """Dibuja la etiqueta y el valor del contador de pulsaciones."""
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
        """Devuelve True si el toque cae dentro del circulo del boton."""
        if not self.visible or not self.enabled:
            return False
        cx, cy = self._btn_center_x, self._btn_center_y
        r = self._btn_radius
        dx = screen_x - cx
        dy = screen_y - cy
        return (dx * dx + dy * dy) <= (r * r)

    def on_touch(self, screen_x: int, screen_y: int) -> bool:
        """Activa el callback de presion si el toque cae dentro del circulo."""
        if self.hit_test(screen_x, screen_y):
            if self._on_press:
                self._on_press()
            return True
        return False


# ═══════════════════════════════════════════════════════════════
# ConfigButton — Botón flotante con icono engranaje (V1.1)
# ═══════════════════════════════════════════════════════════════


class ConfigButton(Widget):
    """Botón flotante pequeño con icono de engranaje, esquina inferior derecha."""

    def __init__(self, parent_w: int, parent_h: int, size: int = 40, margin: int = 10) -> None:
        x = parent_w - size - margin
        y = parent_h - size - margin
        super().__init__(x, y, size, size)
        self._on_click: callable | None = None

    def set_on_click(self, callback: callable) -> None:
        """Registra el callback invocado al tocar el boton de configuracion."""
        self._on_click = callback

    def draw(self, surface: pygame.Surface) -> None:
        """Dibuja el boton flotante con icono de engranaje."""
        if not self.visible:
            return
        cx = self.rect.centerx
        cy = self.rect.centery
        r = self.rect.width // 2 - 2

        # Circle background
        pygame.draw.circle(surface, CONFIG_BTN_BG, (cx, cy), r)
        pygame.draw.circle(surface, TEXT_DIM, (cx, cy), r, 2)

        # Gear icon: center dot + 4 spokes (simple)
        dot_r = 3
        pygame.draw.circle(surface, CONFIG_BTN_ICON, (cx, cy), dot_r)
        import math
        for i in range(6):
            angle = i * math.pi / 3
            spoke_start = dot_r + 3
            spoke_end = r - 5
            x1 = cx + int(spoke_start * math.cos(angle))
            y1 = cy + int(spoke_start * math.sin(angle))
            x2 = cx + int(spoke_end * math.cos(angle))
            y2 = cy + int(spoke_end * math.sin(angle))
            pygame.draw.line(surface, CONFIG_BTN_ICON, (x1, y1), (x2, y2), 2)

        # Outer ring segments
        for i in range(6):
            angle = i * math.pi / 3
            sx = cx + int((r - 2) * math.cos(angle))
            sy = cy + int((r - 2) * math.sin(angle))
            pygame.draw.circle(surface, CONFIG_BTN_ICON, (sx, sy), 2)

    def on_touch(self, screen_x: int, screen_y: int) -> bool:
        """Activa el callback de clic si el toque cae sobre el boton."""
        if self.hit_test(screen_x, screen_y):
            if self._on_click:
                self._on_click()
            return True
        return False


# ═══════════════════════════════════════════════════════════════
# ConfigOverlay — Pantalla de configuración (5 opciones) (V1.3)
# ═══════════════════════════════════════════════════════════════

_ICON_MONITOR = "□"    # monitor
_ICON_TOUCH = "◎"      # touch target
_ICON_NETWORK = "⇄"    # network
_ICON_FONT = "A"       # text/font
_ICON_LOCK = "*"       # contraseña (candado simple, compatible con bitmap)
_ICON_BACK = "←"       # back arrow


class ConfigOverlay(Widget):
    """Overlay de pantalla completa con 6 botones de opción."""

    def __init__(self, w: int, h: int) -> None:
        super().__init__(0, 0, w, h)
        self._on_screen_test: callable | None = None
        self._on_touch_calib: callable | None = None
        self._on_network: callable | None = None
        self._on_font: callable | None = None
        self._on_security: callable | None = None
        self._on_back: callable | None = None

        btn_h = 40
        gap = 6
        btn_w = w - 60
        n = 6
        start_y = (h - (btn_h + gap) * n) // 2 + 16
        self._btn_screen = pygame.Rect((w - btn_w) // 2, start_y, btn_w, btn_h)
        self._btn_calib = pygame.Rect((w - btn_w) // 2, start_y + (btn_h + gap), btn_w, btn_h)
        self._btn_network = pygame.Rect((w - btn_w) // 2, start_y + (btn_h + gap) * 2, btn_w, btn_h)
        self._btn_font = pygame.Rect((w - btn_w) // 2, start_y + (btn_h + gap) * 3, btn_w, btn_h)
        self._btn_security = pygame.Rect((w - btn_w) // 2, start_y + (btn_h + gap) * 4, btn_w, btn_h)
        self._btn_back = pygame.Rect((w - btn_w) // 2, start_y + (btn_h + gap) * 5, btn_w, btn_h)

    def set_callbacks(self, screen_test: callable, touch_calib: callable,
                      network: callable, font: callable, security: callable,
                      back: callable) -> None:
        """Registra los callbacks de las 6 opciones del overlay de configuracion."""
        self._on_screen_test = screen_test
        self._on_touch_calib = touch_calib
        self._on_network = network
        self._on_font = font
        self._on_security = security
        self._on_back = back

    def draw(self, surface: pygame.Surface) -> None:
        """Dibuja el overlay de configuracion a pantalla completa."""
        if not self.visible:
            return
        # Full screen background
        pygame.draw.rect(surface, OVERLAY_BG, self.rect)

        # Title
        title_font = _get_font(FONT_BOLD, FONT_SIZE_TITLE)
        title_text = "CONFIGURACION"
        title_rect = _get_text_rect(title_font, title_text)
        title_x = (self.rect.width - title_rect.width) // 2
        title_y = 8
        _render_text(surface, title_font, title_text, OVERLAY_TITLE, title_x, title_y)

        # Draw 6 option buttons
        self._draw_option(surface, self._btn_screen, "Prueba de Pantalla", _ICON_MONITOR, OPTION_ICON_MONITOR)
        self._draw_option(surface, self._btn_calib, "Calibracion Tactil", _ICON_TOUCH, OPTION_ICON_TOUCH)
        self._draw_option(surface, self._btn_network, "Configurar IP", _ICON_NETWORK, OPTION_ICON_NETWORK)
        self._draw_option(surface, self._btn_font, "Texto y Fuente", _ICON_FONT, OPTION_ICON_FONT)
        self._draw_option(surface, self._btn_security, "Contraseña", _ICON_LOCK, OPTION_ICON_LOCK)
        self._draw_option(surface, self._btn_back, "Volver", _ICON_BACK, OPTION_ICON_BACK)

    def _draw_option(self, surface: pygame.Surface, rect: pygame.Rect,
                     label: str, icon_char: str, icon_color: tuple) -> None:
        """Dibuja una opcion del overlay (icono + etiqueta)."""
        pygame.draw.rect(surface, OPTION_BG, rect)
        pygame.draw.rect(surface, OVERLAY_BORDER, rect, 2)

        icon_font = _get_font(FONT_BOLD, FONT_SIZE_BIG)
        icon_rect = _get_text_rect(icon_font, icon_char)
        icon_x = rect.x + 20
        icon_y = rect.y + (rect.height - icon_rect.height) // 2
        _render_text(surface, icon_font, icon_char, icon_color, icon_x, icon_y)

        label_font = _get_font(FONT_FAMILY, FONT_SIZE_HEADING)
        label_rect = _get_text_rect(label_font, label)
        label_x = rect.x + 60
        label_y = rect.y + (rect.height - label_rect.height) // 2
        _render_text(surface, label_font, label, TEXT_PRIMARY, label_x, label_y)

    def on_touch(self, screen_x: int, screen_y: int) -> bool:
        """Activa el callback de la opcion tocada en el overlay de configuracion."""
        if self._btn_screen.collidepoint(screen_x, screen_y):
            if self._on_screen_test:
                self._on_screen_test()
            return True
        if self._btn_calib.collidepoint(screen_x, screen_y):
            if self._on_touch_calib:
                self._on_touch_calib()
            return True
        if self._btn_network.collidepoint(screen_x, screen_y):
            if self._on_network:
                self._on_network()
            return True
        if self._btn_font.collidepoint(screen_x, screen_y):
            if self._on_font:
                self._on_font()
            return True
        if self._btn_security.collidepoint(screen_x, screen_y):
            if self._on_security:
                self._on_security()
            return True
        if self._btn_back.collidepoint(screen_x, screen_y):
            if self._on_back:
                self._on_back()
            return True
        return False


# ═══════════════════════════════════════════════════════════════
# ScreenTestView — Patrones de prueba de pantalla (V1.1)
# ═══════════════════════════════════════════════════════════════

_SCREEN_PATTERNS = ["Barras", "Colores", "Grid", "Degradado", "Salir"]


class ScreenTestView(Widget):
    """Vista de prueba de pantalla con patrones conmutables."""

    def __init__(self, w: int, h: int) -> None:
        super().__init__(0, 0, w, h)
        self._pattern_idx: int = 0
        self._on_exit: callable | None = None

        # Pattern area (top) and button bar (bottom)
        self._pattern_area = pygame.Rect(0, 0, w, h - 44)
        btn_w = w // len(_SCREEN_PATTERNS)
        self._btn_rects: list[pygame.Rect] = []
        for i in range(len(_SCREEN_PATTERNS)):
            self._btn_rects.append(pygame.Rect(i * btn_w, h - 44, btn_w, 44))

    def set_on_exit(self, callback: callable) -> None:
        """Registra el callback invocado al tocar la opcion 'Salir'."""
        self._on_exit = callback

    def draw(self, surface: pygame.Surface) -> None:
        """Dibuja el patron de prueba actual y la barra de botones inferior."""
        if not self.visible:
            return

        # Draw current pattern
        area = self._pattern_area
        if self._pattern_idx == 0:
            self._draw_color_bars(surface, area)
        elif self._pattern_idx == 1:
            self._draw_solid_colors(surface, area)
        elif self._pattern_idx == 2:
            self._draw_grid(surface, area)
        elif self._pattern_idx == 3:
            self._draw_gradient(surface, area)

        # Draw button bar
        bar_y = self.rect.y + self.rect.height - 44
        pygame.draw.rect(surface, HEADER_BG, (0, bar_y, self.rect.width, 44))

        font = _get_font(FONT_BOLD, FONT_SIZE_SMALL)
        for i, (label, btn) in enumerate(zip(_SCREEN_PATTERNS, self._btn_rects, strict=False)):
            bg = BUTTON_BG if i != self._pattern_idx else CONFIG_BTN_HOVER
            pygame.draw.rect(surface, bg, btn)
            pygame.draw.rect(surface, TEXT_DIM, btn, 1)
            text_rect = _get_text_rect(font, label)
            tx = btn.x + (btn.width - text_rect.width) // 2
            ty = btn.y + (btn.height - text_rect.height) // 2
            _render_text(surface, font, label, BUTTON_TEXT, tx, ty)

    def _draw_color_bars(self, surface: pygame.Surface, area: pygame.Rect) -> None:
        """Dibuja el patron de barras de color (SMPTE-like)."""
        colors = [
            TEST_BAR_W,
            TEST_BAR_Y,
            TEST_BAR_C,
            TEST_BAR_G,
            TEST_BAR_M,
            TEST_BAR_R,
            TEST_BAR_B,
            TEST_BAR_BK,
        ]
        bar_w = area.width // len(colors)
        for i, color in enumerate(colors):
            pygame.draw.rect(surface, color, (area.x + i * bar_w, area.y, bar_w, area.height))

    def _draw_solid_colors(self, surface: pygame.Surface, area: pygame.Rect) -> None:
        """Dibuja celdas de colores solidos con su nombre centrado."""
        colors = [
            ((255, 255, 255), "BLANCO"),
            ((255, 0, 0), "ROJO"),
            ((0, 255, 0), "VERDE"),
            ((0, 0, 255), "AZUL"),
            ((0, 0, 0), "NEGRO"),
        ]
        cell_w = area.width // len(colors)
        font = _get_font(FONT_BOLD, FONT_SIZE_SMALL)
        for i, (color, label) in enumerate(colors):
            rect = pygame.Rect(area.x + i * cell_w, area.y, cell_w, area.height)
            pygame.draw.rect(surface, color, rect)
            # Text in contrasting color
            text_color = (0, 0, 0) if color[0] + color[1] + color[2] > 380 else (255, 255, 255)
            tr = _get_text_rect(font, label)
            tx = rect.centerx - tr.width // 2
            ty = rect.centery - tr.height // 2
            _render_text(surface, font, label, text_color, tx, ty)

    def _draw_grid(self, surface: pygame.Surface, area: pygame.Rect) -> None:
        """Dibuja una rejilla de celdas con colores pseudo-aleatorios (seed fija)."""
        from random import randint, seed
        seed(42)
        cell = 20
        for row in range(0, area.height, cell):
            for col in range(0, area.width, cell):
                color = (randint(20, 240), randint(20, 240), randint(20, 240))
                pygame.draw.rect(surface, color, (area.x + col, area.y + row, cell, cell))

    def _draw_gradient(self, surface: pygame.Surface, area: pygame.Rect) -> None:
        """Dibuja un degradado horizontal de rojo a azul."""
        for x in range(area.width):
            ratio = x / area.width
            r = int(255 * (1 - ratio))
            g = int(50 + 150 * ratio)
            b = int(255 * ratio)
            pygame.draw.line(surface, (r, g, b),
                             (area.x + x, area.y),
                             (area.x + x, area.y + area.height - 1))

    def on_touch(self, screen_x: int, screen_y: int) -> bool:
        """Cambia el patron o sale de la vista segun el boton tocado."""
        for i, btn in enumerate(self._btn_rects):
            if btn.collidepoint(screen_x, screen_y):
                if i == 4:  # Salir
                    if self._on_exit:
                        self._on_exit()
                else:
                    self._pattern_idx = i
                return True
        return False


# ═══════════════════════════════════════════════════════════════
# TouchCalibrationView — Asistente de calibración táctil (V1.1)
# ═══════════════════════════════════════════════════════════════

_CALIB_POINT_NAMES = ["Sup.Izq", "Sup.Der", "Centro", "Inf.Izq", "Inf.Der"]


class TouchCalibrationView(Widget):
    """Asistente de calibración: pide tocar 5 cruces y calcula el mapeo.

    En modo calibración cada toque captura la coordenada RAW del
    dispositivo (no aplica el mapeo actual, que puede estar mal). Con
    5 puntos se resuelve la transformación afín por mínimos cuadrados.
    """

    def __init__(self, w: int, h: int) -> None:
        super().__init__(0, 0, w, h)
        self._current: int = 0
        self._done: bool = False
        self._coeffs: tuple | None = None
        self._offsets: list[tuple] = []
        self._raw_points: list[tuple[int, int, int, int]] = []

        # Puntos de calibración (coordenadas de pantalla)
        self._points: list[tuple[int, int]] = [
            (int(w * 0.08), int(h * 0.15)),
            (int(w * 0.92), int(h * 0.15)),
            (int(w * 0.50), int(h * 0.50)),
            (int(w * 0.08), int(h * 0.85)),
            (int(w * 0.92), int(h * 0.85)),
        ]

    def register_tap(self, raw_x: int, raw_y: int) -> None:
        """Registra un toque (coordenadas RAW) y avanza al siguiente punto."""
        if self._done:
            return
        sx, sy = self._points[self._current]
        logger.info(
            "Calib tap %d/5: raw=(%d,%d) -> target=(%d,%d)",
            self._current + 1, raw_x, raw_y, sx, sy,
        )
        self._raw_points.append((raw_x, raw_y, sx, sy))
        self._current += 1
        if self._current >= len(self._points):
            self._finish()

    def _finish(self) -> None:
        """Valida los puntos capturados y resuelve la transformacion afin.

        Rechaza capturas degeneradas (span raw < 300 en X o Y) reiniciando
        el asistente, y calcula los offsets por punto para mostrarlos en la
        vista de resultados.
        """
        # Validar que los puntos raw capturados no sean degenerados
        rxs = [rx for rx, ry, sx, sy in self._raw_points]
        rys = [ry for rx, ry, sx, sy in self._raw_points]
        span_x = max(rxs) - min(rxs)
        span_y = max(rys) - min(rys)
        logger.info(
            "Calib raw: X[%d..%d] (span %d), Y[%d..%d] (span %d)",
            min(rxs), max(rxs), span_x, min(rys), max(rys), span_y,
        )
        if span_x < 300 or span_y < 300:
            logger.warning(
                "Calibracion degenerada (span raw x=%d y=%d) — reintentando",
                span_x, span_y,
            )
            self.reset()
            return
        try:
            from display.ui.touch import solve_affine
            self._coeffs = solve_affine(self._raw_points)
            a, b, c, d, e, f = self._coeffs
            self._offsets = []
            for rx, ry, sx, sy in self._raw_points:
                cx = a * rx + b * ry + c
                cy = d * rx + e * ry + f
                self._offsets.append((sx, sy, round(cx - sx), round(cy - sy)))
            self._done = True
        except ValueError:
            logger.warning("Calibracion singular — reintentando")
            self.reset()

    @property
    def is_done(self) -> bool:
        """True si se completaron los 5 puntos de calibracion."""
        return self._done

    @property
    def coefficients(self) -> tuple | None:
        """Coeficientes afines resueltos, o None si aun no se completaron."""
        return self._coeffs

    @property
    def raw_points(self) -> list[tuple[int, int, int, int]]:
        """Copia de los puntos (raw_x, raw_y, screen_x, screen_y) capturados."""
        return list(self._raw_points)

    def reset(self) -> None:
        """Reinicia el asistente de calibracion al primer punto."""
        self._current = 0
        self._done = False
        self._coeffs = None
        self._offsets = []
        self._raw_points = []

    def draw(self, surface: pygame.Surface) -> None:
        """Dibuja la cruz de calibracion o la tabla de resultados segun el estado."""
        if not self.visible:
            return
        pygame.draw.rect(surface, CALIB_BG, self.rect)
        if self._done:
            self._draw_results(surface)
        else:
            self._draw_target(surface)

    def _draw_target(self, surface: pygame.Surface) -> None:
        """Dibuja la cruz de calibracion y el progreso actual."""
        title_font = _get_font(FONT_BOLD, FONT_SIZE_TITLE)
        title_text = "CALIBRACION TACTIL"
        title_r = _get_text_rect(title_font, title_text)
        _render_text(surface, title_font, title_text, TARGET_ACTIVE,
                     (self.rect.width - title_r.width) // 2, 12)

        sub_font = _get_font(FONT_FAMILY, FONT_SIZE_SMALL)
        sub_text = f"Toca la cruz iluminada  ({self._current + 1}/5)"
        sub_r = _get_text_rect(sub_font, sub_text)
        _render_text(surface, sub_font, sub_text, CALIB_TEXT,
                     (self.rect.width - sub_r.width) // 2, 34)

        # Cruz actual (grande y visible)
        tx, ty = self._points[self._current]
        ring_r = 18
        pygame.draw.circle(surface, TARGET_RING, (tx, ty), ring_r, 4)
        pygame.draw.circle(surface, TARGET_CENTER, (tx, ty), 4)
        pygame.draw.line(surface, TARGET_RING, (tx - ring_r - 12, ty), (tx - ring_r, ty), 3)
        pygame.draw.line(surface, TARGET_RING, (tx + ring_r, ty), (tx + ring_r + 12, ty), 3)
        pygame.draw.line(surface, TARGET_RING, (tx, ty - ring_r - 12), (tx, ty - ring_r), 3)
        pygame.draw.line(surface, TARGET_RING, (tx, ty + ring_r), (tx, ty + ring_r + 12), 3)

        # Marcar puntos ya completados
        for i in range(self._current):
            px, py = self._points[i]
            pygame.draw.circle(surface, TARGET_TOUCHED, (px, py), 7, 2)

    def _draw_results(self, surface: pygame.Surface) -> None:
        """Dibuja la tabla de resultados (offsets por punto de calibracion)."""
        title_font = _get_font(FONT_BOLD, FONT_SIZE_TITLE)
        if self._coeffs:
            title_text = "Calibracion correcta"
            title_color = SUCCESS
        else:
            title_text = "Error de calibracion"
            title_color = TARGET_RING
        title_r = _get_text_rect(title_font, title_text)
        _render_text(surface, title_font, title_text, title_color,
                     (self.rect.width - title_r.width) // 2, 14)

        row_font = _get_font(FONT_FAMILY, FONT_SIZE_SMALL)
        header_y = 44
        col_x = [20, 130, 240, 340]
        headers = ["Punto", "Target", "Offset X", "Offset Y"]
        for _, (h, x) in enumerate(zip(headers, col_x, strict=False)):
            _render_text(surface, row_font, h, TEXT_SECONDARY, x, header_y)

        for j, off in enumerate(self._offsets):
            y = header_y + 18 + j * 18
            _render_text(surface, row_font, _CALIB_POINT_NAMES[j], CALIB_TEXT, col_x[0], y)
            _render_text(surface, row_font, f"({off[0]},{off[1]})", TEXT_SECONDARY, col_x[1], y)
            ox_color = WARNING if abs(off[2]) > 10 else SUCCESS
            oy_color = WARNING if abs(off[3]) > 10 else SUCCESS
            _render_text(surface, row_font, f"{off[2]:+d}", ox_color, col_x[2], y)
            _render_text(surface, row_font, f"{off[3]:+d}", oy_color, col_x[3], y)

        hint_font = _get_font(FONT_BOLD, FONT_SIZE_HEADING)
        hint_text = "Volviendo al panel principal..."
        hint_r = _get_text_rect(hint_font, hint_text)
        _render_text(surface, hint_font, hint_text, TEXT_SECONDARY,
                     (self.rect.width - hint_r.width) // 2, self.rect.height - 36)


# ═══════════════════════════════════════════════════════════════
# NetworkConfigView — Configuracion de IP (estatica/DHCP) (V1.1)
# ═══════════════════════════════════════════════════════════════


class NetworkConfigView(Widget):
    """Vista de configuracion de IP apta para pantalla tactil.

    Permite elegir entre DHCP (automatico) e IP estatica, editando los
    4 octetos de la IP con flechas +/-. La puerta de enlace y el DNS se
    derivan automaticamente (subnet .1). Para edicion avanzada (gateway
    y DNS personalizados) usar el panel web.
    """

    def __init__(self, w: int, h: int) -> None:
        super().__init__(0, 0, w, h)
        self.mode: str = "dhcp"
        self.octets: list[int] = [192, 168, 88, 200]
        self.prefix: int = 24
        self._info_lines: list[str] = []
        self._result: str = ""
        self._result_error: bool = False
        self._on_apply: callable | None = None
        self._on_back: callable | None = None

        # ── Hit regions ──
        self._btn_dhcp = pygame.Rect(16, 78, 214, 32)
        self._btn_static = pygame.Rect(250, 78, 214, 32)

        self._oct_up: list[pygame.Rect] = []
        self._oct_val: list[pygame.Rect] = []
        self._oct_down: list[pygame.Rect] = []
        for i in range(4):
            x = 20 + i * 120
            self._oct_up.append(pygame.Rect(x, 118, 100, 22))
            self._oct_val.append(pygame.Rect(x, 140, 100, 26))
            self._oct_down.append(pygame.Rect(x, 166, 100, 22))

        self._apply_rect = pygame.Rect(20, 250, 440, 36)
        self._back_rect = pygame.Rect(20, 290, 440, 26)

    def set_on_apply(self, callback: callable) -> None:
        """Registra el callback invocado al tocar 'APLICAR' (recibe el payload)."""
        self._on_apply = callback

    def set_on_back(self, callback: callable) -> None:
        """Registra el callback invocado al tocar 'VOLVER'."""
        self._on_back = callback

    def set_status(self, net: dict) -> None:
        """Rellena el formulario con el estado de red actual (dict JSON)."""
        ip = net.get("ip_address") or ""
        if ip and "." in ip:
            parts = ip.split(".")
            if len(parts) == 4:
                with contextlib.suppress(ValueError):
                    self.octets = [int(p) for p in parts]
        self.mode = "static" if net.get("mode") == "static" else "dhcp"
        self.prefix = net.get("prefix") or 24
        self._info_lines = [
            f"Interfaz: {net.get('interface') or '-'}",
            f"IP actual: {ip or '-'}",
            f"Modo: {'ESTATICA' if self.mode == 'static' else 'DHCP'}",
        ]

    def set_result(self, message: str, error: bool = False) -> None:
        """Muestra un mensaje de resultado (exito o error) en la vista."""
        self._result = message
        self._result_error = error

    @property
    def gateway(self) -> str:
        """Puerta de enlace derivada de los octetos editados (subnet .1)."""
        return f"{self.octets[0]}.{self.octets[1]}.{self.octets[2]}.1"

    def _payload(self) -> dict:
        """Construye el payload JSON que se envia a POST /api/network/static."""
        ip = ".".join(str(o) for o in self.octets)
        return {
            "mode": self.mode,
            "ip_address": ip,
            "prefix": self.prefix,
            "gateway": self.gateway,
            "dns": self.gateway,
        }

    def draw(self, surface: pygame.Surface) -> None:
        """Dibuja la vista de configuracion de IP (DHCP/estatica)."""
        if not self.visible:
            return
        pygame.draw.rect(surface, NETWORK_BG, self.rect)

        # Titulo
        title_font = _get_font(FONT_BOLD, FONT_SIZE_TITLE)
        title_text = "CONFIGURAR IP"
        title_r = _get_text_rect(title_font, title_text)
        _render_text(surface, title_font, title_text, NETWORK_ACCENT,
                     (self.rect.width - title_r.width) // 2, 8)

        # Info actual
        info_font = _get_font(FONT_FAMILY, FONT_SIZE_SMALL)
        for i, line in enumerate(self._info_lines):
            _render_text(surface, info_font, line, NETWORK_DIM, 20, 34 + i * 15)

        # Selector de modo
        self._draw_mode_btn(surface, self._btn_dhcp, "DHCP (auto)", self.mode == "dhcp")
        self._draw_mode_btn(surface, self._btn_static, "IP ESTATICA", self.mode == "static")

        if self.mode == "static":
            self._draw_octets(surface)
            derived_font = _get_font(FONT_FAMILY, FONT_SIZE_SMALL)
            derived = f"Gateway: {self.gateway}   Mascara: /{self.prefix}"
            derived_r = _get_text_rect(derived_font, derived)
            _render_text(surface, derived_font, derived, NETWORK_DIM,
                         (self.rect.width - derived_r.width) // 2, 196)

        # Resultado
        if self._result:
            res_font = _get_font(FONT_BOLD, FONT_SIZE_SMALL)
            res_color = ERROR if self._result_error else SUCCESS
            res_r = _get_text_rect(res_font, self._result)
            _render_text(surface, res_font, self._result, res_color,
                         (self.rect.width - res_r.width) // 2, 218)

        # Aplicar
        pygame.draw.rect(surface, NETWORK_ACCENT, self._apply_rect)
        pygame.draw.rect(surface, NETWORK_FIELD_BORDER, self._apply_rect, 2)
        apply_font = _get_font(FONT_BOLD, FONT_SIZE_HEADING)
        apply_text = "APLICAR"
        apply_r = _get_text_rect(apply_font, apply_text)
        _render_text(surface, apply_font, apply_text, (255, 255, 255),
                     self._apply_rect.x + (self._apply_rect.width - apply_r.width) // 2,
                     self._apply_rect.y + (self._apply_rect.height - apply_r.height) // 2)

        # Volver
        pygame.draw.rect(surface, OPTION_BG, self._back_rect)
        pygame.draw.rect(surface, NETWORK_FIELD_BORDER, self._back_rect, 1)
        back_font = _get_font(FONT_BOLD, FONT_SIZE_SMALL)
        back_text = "VOLVER"
        back_r = _get_text_rect(back_font, back_text)
        _render_text(surface, back_font, back_text, TEXT_SECONDARY,
                     self._back_rect.x + (self._back_rect.width - back_r.width) // 2,
                     self._back_rect.y + (self._back_rect.height - back_r.height) // 2)

    def _draw_mode_btn(self, surface: pygame.Surface, rect: pygame.Rect,
                       label: str, active: bool) -> None:
        """Dibuja un boton de seleccion de modo (DHCP/estatica)."""
        bg = NETWORK_ACTIVE if active else NETWORK_FIELD_BG
        border = NETWORK_ACTIVE if active else NETWORK_FIELD_BORDER
        pygame.draw.rect(surface, bg, rect)
        pygame.draw.rect(surface, border, rect, 2)
        font = _get_font(FONT_BOLD, FONT_SIZE_SMALL)
        text_r = _get_text_rect(font, label)
        _render_text(surface, font, label, (255, 255, 255) if active else NETWORK_TEXT,
                     rect.x + (rect.width - text_r.width) // 2,
                     rect.y + (rect.height - text_r.height) // 2)

    def _draw_octets(self, surface: pygame.Surface) -> None:
        """Dibuja los 4 octetos de la IP con flechas arriba/abajo."""
        for i in range(4):
            up = self._oct_up[i]
            val = self._oct_val[i]
            down = self._oct_down[i]

            # Flecha arriba
            pygame.draw.rect(surface, NETWORK_STEP_BG, up)
            pygame.draw.rect(surface, NETWORK_FIELD_BORDER, up, 1)
            self._draw_arrow(surface, up, up=True)

            # Valor
            pygame.draw.rect(surface, NETWORK_FIELD_BG, val)
            pygame.draw.rect(surface, NETWORK_FIELD_BORDER, val, 1)
            val_font = _get_font(FONT_BOLD, FONT_SIZE_HEADING)
            val_text = str(self.octets[i])
            val_r = _get_text_rect(val_font, val_text)
            _render_text(surface, val_font, val_text, NETWORK_TEXT,
                         val.x + (val.width - val_r.width) // 2,
                         val.y + (val.height - val_r.height) // 2)

            # Flecha abajo
            pygame.draw.rect(surface, NETWORK_STEP_BG, down)
            pygame.draw.rect(surface, NETWORK_FIELD_BORDER, down, 1)
            self._draw_arrow(surface, down, up=False)

    def _draw_arrow(self, surface: pygame.Surface, rect: pygame.Rect, up: bool) -> None:
        """Dibuja una flecha triangular (arriba o abajo) en el rectangulo dado."""
        cx = rect.centerx
        if up:
            y1 = rect.y + rect.height - 5
            y2 = rect.y + 5
        else:
            y1 = rect.y + 5
            y2 = rect.y + rect.height - 5
        pygame.draw.polygon(surface, NETWORK_TEXT, [(cx - 5, y1), (cx + 5, y1), (cx, y2)])

    def on_touch(self, screen_x: int, screen_y: int) -> bool:
        """Maneja la interaccion: seleccion de modo, edicion de octetos y aplicar."""
        if self._btn_dhcp.collidepoint(screen_x, screen_y):
            self.mode = "dhcp"
            return True
        if self._btn_static.collidepoint(screen_x, screen_y):
            self.mode = "static"
            return True
        if self.mode == "static":
            for i in range(4):
                if self._oct_up[i].collidepoint(screen_x, screen_y):
                    self.octets[i] = min(255, self.octets[i] + 1)
                    return True
                if self._oct_down[i].collidepoint(screen_x, screen_y):
                    self.octets[i] = max(0, self.octets[i] - 1)
                    return True
        if self._apply_rect.collidepoint(screen_x, screen_y):
            if self._on_apply:
                self._on_apply(self._payload())
            return True
        if self._back_rect.collidepoint(screen_x, screen_y):
            if self._on_back:
                self._on_back()
            return True
        return False


# ═══════════════════════════════════════════════════════════════
# FontSettingsView — Configuracion de fuente y tamano de texto (V1.3)
# ═══════════════════════════════════════════════════════════════

_FONT_LABELS = {"dejavu": "DejaVu Sans", "liberation": "Liberation Sans"}
_SIZE_LABELS = {"small": "Pequeno", "medium": "Medio", "large": "Grande"}


class FontSettingsView(Widget):
    """Vista de seleccion de fuente y tamano apta para pantalla tactil.

    Muestra dos familias (DejaVu Sans / Liberation Sans) y tres tamanos
    (Pequeno / Medio / Grande). Al tocar una opcion se aplica al instante
    y se notifica via callback para persistir en el backend.
    """

    def __init__(self, w: int, h: int) -> None:
        super().__init__(0, 0, w, h)
        self.font_family: str = "dejavu"
        self.text_size: str = "medium"
        self._on_change: callable | None = None
        self._on_back: callable | None = None

        # ── Hit regions ──
        self._font_btns = {
            "dejavu": pygame.Rect(20, 64, 210, 44),
            "liberation": pygame.Rect(250, 64, 210, 44),
        }
        self._size_btns = {
            "small": pygame.Rect(20, 150, 140, 44),
            "medium": pygame.Rect(170, 150, 140, 44),
            "large": pygame.Rect(320, 150, 140, 44),
        }
        self._back_rect = pygame.Rect(20, 268, 440, 42)

    def set_on_change(self, callback: callable) -> None:
        """Registra el callback invocado al cambiar fuente o tamano (familia, tamano)."""
        self._on_change = callback

    def set_on_back(self, callback: callable) -> None:
        """Registra el callback invocado al tocar 'VOLVER'."""
        self._on_back = callback

    def set_selection(self, font_family: str, text_size: str) -> None:
        """Sincroniza la seleccion actual (llamado al abrir la vista)."""
        if font_family in _FONT_LABELS:
            self.font_family = font_family
        if text_size in _SIZE_LABELS:
            self.text_size = text_size

    def draw(self, surface: pygame.Surface) -> None:
        """Dibuja la vista de seleccion de fuente y tamano de texto."""
        if not self.visible:
            return
        pygame.draw.rect(surface, NETWORK_BG, self.rect)

        # Titulo
        title_font = _get_font(FONT_BOLD, FONT_SIZE_TITLE)
        title_text = "TEXTO Y FUENTE"
        title_r = _get_text_rect(title_font, title_text)
        _render_text(surface, title_font, title_text, NETWORK_ACCENT,
                     (self.rect.width - title_r.width) // 2, 8)

        # Seccion Fuente
        sec_font = _get_font(FONT_FAMILY, FONT_SIZE_SMALL)
        _render_text(surface, sec_font, "FUENTE", TEXT_SECONDARY, 20, 44)

        for key, rect in self._font_btns.items():
            self._draw_choice(surface, rect, _FONT_LABELS[key], key == self.font_family)

        # Seccion Tamano
        _render_text(surface, sec_font, "TAMANO DEL TEXTO", TEXT_SECONDARY, 20, 130)

        for key, rect in self._size_btns.items():
            self._draw_choice(surface, rect, _SIZE_LABELS[key], key == self.text_size)

        # Volver
        pygame.draw.rect(surface, OPTION_BG, self._back_rect)
        pygame.draw.rect(surface, NETWORK_FIELD_BORDER, self._back_rect, 1)
        back_font = _get_font(FONT_BOLD, FONT_SIZE_HEADING)
        back_text = "VOLVER"
        back_r = _get_text_rect(back_font, back_text)
        _render_text(surface, back_font, back_text, TEXT_SECONDARY,
                     self._back_rect.x + (self._back_rect.width - back_r.width) // 2,
                     self._back_rect.y + (self._back_rect.height - back_r.height) // 2)

    def _draw_choice(self, surface: pygame.Surface, rect: pygame.Rect,
                     label: str, active: bool) -> None:
        """Dibuja una opcion seleccionable de fuente o tamano."""
        bg = NETWORK_ACTIVE if active else NETWORK_FIELD_BG
        border = NETWORK_ACTIVE if active else NETWORK_FIELD_BORDER
        pygame.draw.rect(surface, bg, rect)
        pygame.draw.rect(surface, border, rect, 2)
        font = _get_font(FONT_BOLD, FONT_SIZE_HEADING)
        text_r = _get_text_rect(font, label)
        color = (255, 255, 255) if active else NETWORK_TEXT
        _render_text(surface, font, label, color,
                     rect.x + (rect.width - text_r.width) // 2,
                     rect.y + (rect.height - text_r.height) // 2)

    def on_touch(self, screen_x: int, screen_y: int) -> bool:
        """Aplica la fuente o tamano seleccionado, o vuelve a la vista anterior."""
        for key, rect in self._font_btns.items():
            if rect.collidepoint(screen_x, screen_y):
                self.font_family = key
                if self._on_change:
                    self._on_change(self.font_family, self.text_size)
                return True
        for key, rect in self._size_btns.items():
            if rect.collidepoint(screen_x, screen_y):
                self.text_size = key
                if self._on_change:
                    self._on_change(self.font_family, self.text_size)
                return True
        if self._back_rect.collidepoint(screen_x, screen_y):
            if self._on_back:
                self._on_back()
            return True
        return False


# ═══════════════════════════════════════════════════════════════
# SecuritySettingsView — Gestion de contraseña (FASE 7c)
# ═══════════════════════════════════════════════════════════════

_FIELD_LABELS = {"current": "ACTUAL", "new": "NUEVA", "confirm": "CONFIRMAR"}
_KEY_ROWS = [
    ["1", "2", "3", "BORRAR"],
    ["4", "5", "6", "LIMPIAR"],
    ["7", "8", "9", "0"],
]


class SecuritySettingsView(Widget):
    """Vista de gestion de contraseña apta para pantalla tactil.

    Permite ver el estado de la proteccion por contraseña (activada/desactivada
    y de fabrica/personalizada), activar/desactivar la proteccion y cambiar la
    contraseña usando un teclado numerico en pantalla (0-9 + BORRAR + LIMPIAR).

    Limitacion: desde la pantalla fisica solo se pueden introducir contraseñas
    numericas; para contraseñas alfanumericas usar el panel web.
    """

    _MAX_LEN = 16

    def __init__(self, w: int, h: int) -> None:
        super().__init__(0, 0, w, h)
        self._enabled: bool = False
        self._is_default: bool = True
        self.current: str = ""
        self.new: str = ""
        self.confirm: str = ""
        self._active_field: str = "current"
        self._result: str = ""
        self._result_error: bool = False
        self._on_toggle: callable | None = None
        self._on_change: callable | None = None
        self._on_back: callable | None = None

        # ── Hit regions ──
        self._field_rects: dict[str, pygame.Rect] = {
            "current": pygame.Rect(12, 54, 300, 30),
            "new": pygame.Rect(12, 92, 300, 30),
            "confirm": pygame.Rect(12, 130, 300, 30),
        }
        self._toggle_rect = pygame.Rect(320, 54, 148, 30)
        self._change_rect = pygame.Rect(320, 92, 148, 68)
        self._back_rect = pygame.Rect(12, 284, 456, 30)

        # Teclado numerico (4 columnas x 3 filas)
        self._key_rects: list[tuple[pygame.Rect, str]] = []
        key_x = 12
        key_y = 168
        cell_w = 108
        cell_h = 28
        gap = 6
        for row, keys in enumerate(_KEY_ROWS):
            for col, key in enumerate(keys):
                rect = pygame.Rect(
                    key_x + col * (cell_w + gap),
                    key_y + row * (cell_h + gap),
                    cell_w,
                    cell_h,
                )
                self._key_rects.append((rect, key))

    def set_on_toggle(self, callback: callable) -> None:
        """Registra el callback invocado al tocar ACTIVAR/DESACTIVAR (enabled, current)."""
        self._on_toggle = callback

    def set_on_change(self, callback: callable) -> None:
        """Registra el callback invocado al tocar CAMBIAR (current, new)."""
        self._on_change = callback

    def set_on_back(self, callback: callable) -> None:
        """Registra el callback invocado al tocar VOLVER."""
        self._on_back = callback

    def set_status(self, data: dict) -> None:
        """Actualiza el estado mostrado (enabled, is_default)."""
        self._enabled = bool(data.get("enabled", False))
        self._is_default = bool(data.get("is_default", False))

    def set_result(self, message: str, error: bool = False) -> None:
        """Muestra un mensaje de resultado (exito o error)."""
        self._result = message
        self._result_error = error

    def clear_fields(self) -> None:
        """Vacia los campos editables y devuelve el foco al campo actual."""
        self.current = ""
        self.new = ""
        self.confirm = ""
        self._active_field = "current"

    def draw(self, surface: pygame.Surface) -> None:
        """Dibuja la vista de gestion de contraseña con teclado numerico."""
        if not self.visible:
            return
        pygame.draw.rect(surface, NETWORK_BG, self.rect)

        # Titulo
        title_font = _get_font(FONT_BOLD, FONT_SIZE_TITLE)
        title_text = "CONTRASEÑA"
        title_r = _get_text_rect(title_font, title_text)
        _render_text(surface, title_font, title_text, NETWORK_ACCENT,
                     (self.rect.width - title_r.width) // 2, 4)

        # Estado
        info_font = _get_font(FONT_FAMILY, FONT_SIZE_SMALL)
        proteccion = "ACTIVADA" if self._enabled else "DESACTIVADA"
        contraseña = "DE FABRICA (1234)" if self._is_default else "PERSONALIZADA"
        _render_text(surface, info_font, f"Proteccion: {proteccion}", NETWORK_DIM, 12, 26)
        _render_text(surface, info_font, f"Contraseña: {contraseña}", NETWORK_DIM, 12, 40)

        # Campos editables
        for key, rect in self._field_rects.items():
            self._draw_field(surface, rect, key)

        # Botones de accion
        self._draw_action_btn(surface, self._toggle_rect,
                              "DESACTIVAR" if self._enabled else "ACTIVAR")
        self._draw_action_btn(surface, self._change_rect, "CAMBIAR")

        # Teclado numerico
        for rect, key in self._key_rects:
            self._draw_key(surface, rect, key)

        # Resultado
        if self._result:
            res_font = _get_font(FONT_BOLD, FONT_SIZE_SMALL)
            res_color = ERROR if self._result_error else SUCCESS
            res_r = _get_text_rect(res_font, self._result)
            _render_text(surface, res_font, self._result, res_color,
                         (self.rect.width - res_r.width) // 2, 268)

        # Volver
        pygame.draw.rect(surface, OPTION_BG, self._back_rect)
        pygame.draw.rect(surface, NETWORK_FIELD_BORDER, self._back_rect, 1)
        back_font = _get_font(FONT_BOLD, FONT_SIZE_HEADING)
        back_text = "VOLVER"
        back_r = _get_text_rect(back_font, back_text)
        _render_text(surface, back_font, back_text, TEXT_SECONDARY,
                     self._back_rect.x + (self._back_rect.width - back_r.width) // 2,
                     self._back_rect.y + (self._back_rect.height - back_r.height) // 2)

    def _draw_field(self, surface: pygame.Surface, rect: pygame.Rect, key: str) -> None:
        """Dibuja un campo editable con su etiqueta y valor enmascarado."""
        active = key == self._active_field
        border = NETWORK_ACTIVE if active else NETWORK_FIELD_BORDER
        pygame.draw.rect(surface, NETWORK_FIELD_BG, rect)
        pygame.draw.rect(surface, border, rect, 2 if active else 1)

        label_font = _get_font(FONT_FAMILY, FONT_SIZE_SMALL)
        label_r = _get_text_rect(label_font, _FIELD_LABELS[key])
        _render_text(surface, label_font, _FIELD_LABELS[key], TEXT_SECONDARY,
                     rect.x + 8, rect.centery - label_r.height // 2)

        value = getattr(self, key)
        val_font = _get_font(FONT_BOLD, FONT_SIZE_HEADING)
        display = "*" * len(value)
        val_r = _get_text_rect(val_font, display)
        _render_text(surface, val_font, display, NETWORK_TEXT,
                     rect.x + 90, rect.centery - val_r.height // 2)

    def _draw_action_btn(self, surface: pygame.Surface, rect: pygame.Rect,
                         label: str) -> None:
        """Dibuja un boton de accion (ACTIVAR/DESACTIVAR o CAMBIAR)."""
        pygame.draw.rect(surface, NETWORK_ACCENT, rect)
        pygame.draw.rect(surface, NETWORK_FIELD_BORDER, rect, 2)
        font = _get_font(FONT_BOLD, FONT_SIZE_HEADING)
        text_r = _get_text_rect(font, label)
        _render_text(surface, font, label, (255, 255, 255),
                     rect.x + (rect.width - text_r.width) // 2,
                     rect.y + (rect.height - text_r.height) // 2)

    def _draw_key(self, surface: pygame.Surface, rect: pygame.Rect, key: str) -> None:
        """Dibuja una tecla del teclado numerico."""
        pygame.draw.rect(surface, NETWORK_STEP_BG, rect)
        pygame.draw.rect(surface, NETWORK_FIELD_BORDER, rect, 1)
        font = _get_font(FONT_BOLD, FONT_SIZE_HEADING)
        text_r = _get_text_rect(font, key)
        _render_text(surface, font, key, NETWORK_TEXT,
                     rect.x + (rect.width - text_r.width) // 2,
                     rect.y + (rect.height - text_r.height) // 2)

    def on_touch(self, screen_x: int, screen_y: int) -> bool:
        """Maneja la interaccion: campos, teclado, toggle, cambiar y volver."""
        for key, rect in self._field_rects.items():
            if rect.collidepoint(screen_x, screen_y):
                self._active_field = key
                return True
        for rect, key in self._key_rects:
            if rect.collidepoint(screen_x, screen_y):
                self._handle_key(key)
                return True
        if self._toggle_rect.collidepoint(screen_x, screen_y):
            self._handle_toggle()
            return True
        if self._change_rect.collidepoint(screen_x, screen_y):
            self._handle_change()
            return True
        if self._back_rect.collidepoint(screen_x, screen_y):
            if self._on_back:
                self._on_back()
            return True
        return False

    def _handle_key(self, key: str) -> None:
        """Aplica una tecla del keypad al campo activo (digito/BORRAR/LIMPIAR)."""
        value = getattr(self, self._active_field)
        if key == "BORRAR":
            setattr(self, self._active_field, value[:-1])
        elif key == "LIMPIAR":
            setattr(self, self._active_field, "")
        elif len(value) < self._MAX_LEN:
            setattr(self, self._active_field, value + key)

    def _handle_toggle(self) -> None:
        """Valida y lanza el callback de activar/desactivar la proteccion."""
        target = not self._enabled
        if target and self._is_default:
            self.set_result(
                "Debes cambiar la contraseña de fábrica (1234) antes de activar",
                error=True,
            )
            return
        if not self.current:
            self.set_result("Introduce la contraseña actual", error=True)
            return
        if self._on_toggle:
            self._on_toggle(target, self.current)

    def _handle_change(self) -> None:
        """Valida y lanza el callback de cambio de contraseña."""
        if not self.current:
            self.set_result("Introduce la contraseña actual", error=True)
            return
        if len(self.new) < 8:
            self.set_result("La nueva contraseña debe tener al menos 8 caracteres", error=True)
            return
        if self.new != self.confirm:
            self.set_result("Las contraseñas no coinciden", error=True)
            return
        if self._on_change:
            self._on_change(self.current, self.new)
