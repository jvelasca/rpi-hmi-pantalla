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
