"""Theme — Colores, fuentes y constantes visuales para la UI Pygame.

Define la paleta de color oscura profesional y las dimensiones
base del layout responsive para la pantalla ILI9486 480x320.
"""

from __future__ import annotations

# ── Resolución base (ILI9486 3.5") ────────────────────────────
BASE_WIDTH: int = 480
BASE_HEIGHT: int = 320

# ── Paleta de colores ─────────────────────────────────────────

# Fondo general
BACKGROUND = (20, 20, 40)        # #141428 — azul muy oscuro

# Paneles
PANEL_BG = (30, 30, 60)          # #1e1e3c
PANEL_BORDER = (50, 50, 100)     # #323264

# Header
HEADER_BG = (15, 15, 35)         # #0f0f23
HEADER_TEXT = (233, 69, 96)      # #e94560 — rojo coral (acento)

# Texto
TEXT_PRIMARY = (220, 220, 240)   # #dcdcf0
TEXT_SECONDARY = (160, 160, 180) # #a0a0b4
TEXT_DIM = (100, 100, 120)       # #646478

# LED
LED_ON_GLOW = (40, 0, 0)          # halo oscuro
LED_ON_MID = (120, 0, 0)          # halo medio
LED_ON_CORE = (255, 0, 0)         # rojo intenso
LED_ON_HIGHLIGHT = (255, 100, 80) # brillo especular
LED_OFF_BG = (60, 60, 60)         # gris apagado
LED_OFF_MID = (80, 80, 80)
LED_OFF_HIGHLIGHT = (120, 120, 120)

# LED 2 (boton PULSAR, verde)
LED2_ON_GLOW = (0, 40, 20)
LED2_ON_MID = (0, 120, 60)
LED2_ON_CORE = (0, 255, 100)
LED2_ON_HIGHLIGHT = (140, 255, 190)

# Botón
BUTTON_BG = (15, 52, 96)           # #0f3460
BUTTON_HOVER = (25, 75, 140)       # #194b8c
BUTTON_PRESSED = (8, 30, 60)       # #081e3c
BUTTON_TEXT = (255, 255, 255)      # blanco

# Botón circular (HMI)
BTN_IDLE_BG = (15, 52, 96)
BTN_IDLE_MID = (30, 80, 140)
BTN_PRESSED_BG = (0, 50, 0)
BTN_PRESSED_MID = (0, 180, 60)
BTN_PRESSED_TEXT = (0, 255, 100)

# Estados
SUCCESS = (0, 255, 100)           # verde
WARNING = (255, 200, 0)           # amarillo
ERROR = (255, 60, 60)             # rojo

# Footer
FOOTER_BG = (0, 0, 0)             # negro
FOOTER_TEXT = (68, 68, 68)        # gris tenue

# ── Layout (proporciones, 480x320 base) ───────────────────────
HEADER_HEIGHT: int = 36
FOOTER_HEIGHT: int = 22
MARGIN: int = 10

# Panel izquierdo (LED) — ~38% del ancho
LED_PANEL_X: int = 10
LED_PANEL_W: int = 180

# Panel derecho (Botón) — ~38% del ancho
BTN_PANEL_W: int = 180

# ── Config button ────────────────────────────────────────────
CONFIG_BTN_BG = (15, 52, 96)        # #0f3460 — igual que BUTTON_BG
CONFIG_BTN_HOVER = (25, 75, 140)    # #194b8c
CONFIG_BTN_ICON = (200, 200, 220)   # #c8c8dc

# ── Config overlay ──────────────────────────────────────────
OVERLAY_BG = (10, 10, 30)           # #0a0a1e — casi negro
OVERLAY_BORDER = (50, 50, 100)      # #323264
OVERLAY_TITLE = (233, 69, 96)       # #e94560 — rojo coral
OPTION_BG = (20, 40, 80)            # #142850
OPTION_HOVER = (30, 60, 120)        # #1e3c78
OPTION_ICON_MONITOR = (0, 200, 255) # cyan
OPTION_ICON_TOUCH = (255, 180, 0)   # naranja
OPTION_ICON_NETWORK = (255, 184, 74)  # ambar
OPTION_ICON_FONT = (190, 130, 255)  # violeta
OPTION_ICON_LOCK = (255, 130, 170)  # rosa (contrasena)
OPTION_ICON_BACK = (160, 160, 180)  # gris claro

# ── Screen test ─────────────────────────────────────────────
TEST_BAR_R = (255, 0, 0)
TEST_BAR_G = (0, 255, 0)
TEST_BAR_B = (0, 0, 255)
TEST_BAR_Y = (255, 255, 0)
TEST_BAR_C = (0, 255, 255)
TEST_BAR_M = (255, 0, 255)
TEST_BAR_W = (255, 255, 255)
TEST_BAR_BK = (0, 0, 0)
TEST_GRID_COLOR = (60, 60, 80)

# ── Touch calibration ───────────────────────────────────────
TARGET_RING = (255, 60, 60)          # rojo
TARGET_CENTER = (255, 255, 255)      # blanco
TARGET_TOUCHED = (0, 255, 100)       # verde
TARGET_ACTIVE = (255, 200, 0)        # amarillo
CALIB_BG = (15, 15, 35)              # #0f0f23
CALIB_TEXT = (220, 220, 240)         # #dcdcf0

# ── Network config ─────────────────────────────────────────
NETWORK_BG = (15, 15, 35)            # #0f0f23
NETWORK_TEXT = (220, 220, 240)       # #dcdcf0
NETWORK_FIELD_BG = (20, 40, 80)      # #142850
NETWORK_FIELD_BORDER = (50, 50, 100) # #323264
NETWORK_ACTIVE = (74, 158, 255)      # #4a9eff
NETWORK_ACCENT = (233, 69, 96)       # #e94560
NETWORK_DIM = (100, 100, 120)        # #646478
NETWORK_STEP_BG = (25, 75, 140)      # #194b8c

# ── Fuentes ───────────────────────────────────────────────────
# Pygame freetype usa paths o nombres de sistema.
# En Raspberry Pi Bookworm: DejaVu Sans está disponible.
FONT_FAMILY: str = "DejaVuSans"
FONT_BOLD: str = "DejaVuSans-Bold"
FONT_SIZE_TITLE: int = 16
FONT_SIZE_HEADING: int = 14
FONT_SIZE_NORMAL: int = 12
FONT_SIZE_SMALL: int = 10
FONT_SIZE_COUNTER: int = 28
FONT_SIZE_BIG: int = 20

# ── Fuentes configurables (pantalla pequeña 480x320) ──────────
# Registro de familias soportadas con sus rutas TTF (regular y bold).
# Ambas fuentes están presentes en Raspberry Pi OS (Bookworm).
FONT_FAMILIES: dict[str, dict[str, str | list[str]]] = {
    "dejavu": {
        "label": "DejaVu Sans",
        "regular": [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
        ],
        "bold": [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
        ],
    },
    "liberation": {
        "label": "Liberation Sans",
        "regular": [
            "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        ],
        "bold": [
            "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        ],
    },
}

# Escalas de tamaño de texto compatibles con la pantalla pequeña.
# Se aplican como factor sobre los tamaños base (FONT_SIZE_*).
TEXT_SIZES: dict[str, float] = {
    "small": 0.85,
    "medium": 1.0,
    "large": 1.2,
}

DEFAULT_FONT_FAMILY: str = "dejavu"
DEFAULT_TEXT_SIZE: str = "medium"

_current_font_family: str = DEFAULT_FONT_FAMILY
_current_text_size: str = DEFAULT_TEXT_SIZE


def set_font_settings(font_family: str, text_size: str) -> None:
    """Actualiza la familia y escala de texto activas.

    Args:
        font_family: Clave de FONT_FAMILIES ('dejavu' | 'liberation').
        text_size: Clave de TEXT_SIZES ('small' | 'medium' | 'large').
    """
    global _current_font_family, _current_text_size
    _current_font_family = font_family if font_family in FONT_FAMILIES else DEFAULT_FONT_FAMILY
    _current_text_size = text_size if text_size in TEXT_SIZES else DEFAULT_TEXT_SIZE


def get_font_settings() -> dict[str, str]:
    """Devuelve los ajustes de fuente activos."""
    return {"font_family": _current_font_family, "text_size": _current_text_size}


def get_font_scale() -> float:
    """Devuelve el factor de escala de texto activo."""
    return TEXT_SIZES.get(_current_text_size, 1.0)


def get_font_paths(bold: bool) -> list[str]:
    """Devuelve las rutas TTF para la familia activa (regular o bold)."""
    key = "bold" if bold else "regular"
    return list(FONT_FAMILIES[_current_font_family][key])  # type: ignore[arg-type]
