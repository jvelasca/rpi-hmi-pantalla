"""Screen — Gestor de pantalla Pygame con DRM/KMS.

Inicializa Pygame usando el driver KMS/DRM para acceso directo
al hardware sin X11/Wayland. Soporta modo mock para desarrollo
en PC sin display físico.

Uso típico:
    screen = Screen(auto_detect=True)
    surface = screen.get_surface()
    # ... dibujar widgets ...
    screen.flip()
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

import pygame

from display.ui.theme import BACKGROUND, BASE_HEIGHT, BASE_WIDTH

logger = logging.getLogger("rpi_hmi.display.screen")


def _drm_connector_state() -> str:
    """Lee el estado de los conectores DRM vía sysfs.

    Returns:
        "connected"    si al menos un conector reporta "connected".
        "disconnected" si todos los conectores legibles reportan lo contrario.
        "unknown"      si no hay sysfs DRM o no es legible.
    """
    status_files = sorted(Path("/sys/class/drm").glob("card0-*/status"))
    if not status_files:
        return "unknown"

    connected = False
    readable = False
    for status_file in status_files:
        try:
            state = status_file.read_text().strip().lower()
        except OSError:
            continue
        readable = True
        if state == "connected":
            connected = True

    if not readable:
        return "unknown"
    return "connected" if connected else "disconnected"


def _detect_display() -> tuple[str, str, int, int]:
    """Detecta la configuración del display físico.

    Prioridad:
    1. /dev/dri/card0 con conector conectado (o estado desconocido) → DRM/KMS
    2. /dev/fb1       → Framebuffer ILI9486
    3. Fallback        → Mock mode (480x320 ventana)

    En PC (Windows/sin DRM) no existen /dev/dri ni /dev/fb, por lo que
    la detección resuelve a mock.

    Returns:
        (driver_type, device_path, width, height)
    """
    if Path("/dev/dri/card0").exists():
        state = _drm_connector_state()
        if state in ("connected", "unknown"):
            return ("drm", "/dev/dri/card0", BASE_WIDTH, BASE_HEIGHT)
        # Conector desconectado: probar framebuffer antes que mock
    if Path("/dev/fb1").exists():
        return ("fb", "/dev/fb1", BASE_WIDTH, BASE_HEIGHT)
    return ("mock", "", BASE_WIDTH, BASE_HEIGHT)


class Screen:
    """Gestor de la superficie de renderizado Pygame.

    En modo DRM/KMS:
        - Usa SDL_VIDEODRIVER=kmsdrm
        - Acceso directo al hardware sin servidor gráfico
        - Dirty rectangles automáticos de SDL2

    En modo mock (desarrollo en PC):
        - Ventana de 480x320 con título "RPi HMI [MOCK]"

    Atributos:
        width: Ancho de la superficie en píxeles.
        height: Alto de la superficie en píxeles.
        driver: Tipo de driver ("drm", "fb", "mock").
        surface: pygame.Surface principal.
        clock: pygame.time.Clock para control de FPS.
    """

    def __init__(
        self,
        auto_detect: bool = True,
        width: int = BASE_WIDTH,
        height: int = BASE_HEIGHT,
        driver: str = "drm",
        device: str = "/dev/dri/card0",
        fullscreen: bool = True,
        mock: bool = False,
        allow_mock_fallback: bool = True,
    ) -> None:
        self.width = width
        self.height = height
        self.driver = driver
        self.device = device
        self.fullscreen = fullscreen
        self.mock = mock
        self.allow_mock_fallback = allow_mock_fallback

        if auto_detect:
            detected = _detect_display()
            self.driver, self.device, self.width, self.height = detected
            if self.driver == "mock":
                self.mock = True

        self.surface: pygame.Surface | None = None
        self.clock: pygame.time.Clock | None = None
        self._initialized = False

    def init(self) -> bool:
        """Inicializa Pygame y crea la superficie de renderizado.

        Returns:
            True si la inicialización fue exitosa.
        """
        if self._initialized:
            return True

        try:
            if self.mock or self.driver == "mock":
                self._init_mock()
            else:
                self._init_drm()

            self.clock = pygame.time.Clock()
            self._initialized = True

            actual_w, actual_h = self.surface.get_size() if self.surface else (0, 0)
            logger.info(
                "Screen inicializado: %dx%d, driver=%s, mock=%s",
                actual_w, actual_h, self.driver, self.mock,
            )
            return True

        except Exception as exc:
            logger.error("Error inicializando Pygame: %s", exc)
            if self.allow_mock_fallback and not self.mock:
                logger.info("Reintentando en modo mock...")
                self.mock = True
                return self.init()
            return False

    def _init_font_module(self) -> None:
        """Inicializa el modulo de fuentes (freetype o fallback a font)."""
        if hasattr(pygame, "freetype"):
            pygame.freetype.init()
            logger.debug("pygame.freetype inicializado")
        else:
            pygame.font.init()
            logger.debug("pygame.font inicializado (freetype no disponible)")

    def _init_drm(self) -> None:
        """Inicializa Pygame con el driver KMS/DRM."""
        os.environ["SDL_VIDEODRIVER"] = "kmsdrm"
        os.environ["SDL_KMSDRM_DEVICE_INDEX"] = "0"

        # Evitar que Pygame intente usar X11
        os.environ.pop("DISPLAY", None)

        pygame.display.init()
        self._init_font_module()

        flags = pygame.FULLSCREEN if self.fullscreen else 0
        if self.fullscreen:
            # (0, 0) → Pygame usa la resolución nativa del display
            self.surface = pygame.display.set_mode((0, 0), flags)
            self.width, self.height = self.surface.get_size()
        else:
            self.surface = pygame.display.set_mode((self.width, self.height), flags)

        pygame.mouse.set_visible(False)
        logger.info("DRM/KMS inicializado: %dx%d", self.width, self.height)

    def _init_mock(self) -> None:
        """Inicializa Pygame en modo mock (ventana en PC)."""
        pygame.display.init()
        self._init_font_module()

        caption = "RPi HMI [MOCK] — Display Simulado"
        self.surface = pygame.display.set_mode((self.width, self.height))
        pygame.display.set_caption(caption)
        pygame.mouse.set_visible(True)

        logger.info("Mock display inicializado: %dx%d", self.width, self.height)

    def get_surface(self) -> pygame.Surface:
        """Devuelve la superficie de renderizado principal."""
        if self.surface is None:
            raise RuntimeError("Screen no inicializado. Llama a init() primero.")
        return self.surface

    def clear(self) -> None:
        """Limpia la pantalla con el color de fondo."""
        if self.surface:
            self.surface.fill(BACKGROUND)

    def flip(self) -> None:
        """Actualiza la pantalla (swap buffers en DRM, flip en mock)."""
        if self.surface:
            pygame.display.flip()

    def tick(self, fps: int = 30) -> float:
        """Limita los FPS y devuelve el delta time en segundos.

        Args:
            fps: Fotogramas por segundo objetivo.

        Returns:
            Delta time desde el último tick en segundos.
        """
        if self.clock:
            return self.clock.tick(fps) / 1000.0
        return 0.0

    def get_fps(self) -> float:
        """Devuelve los FPS actuales."""
        if self.clock:
            return self.clock.get_fps()
        return 0.0

    def handle_quit(self, event: pygame.event.Event) -> bool:
        """Maneja eventos de salida (QUIT, KEYDOWN ESC).

        Returns:
            True si se debe salir de la aplicación.
        """
        if event.type == pygame.QUIT:
            return True
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                return True
            if event.key == pygame.K_q and (pygame.key.get_mods() & pygame.KMOD_CTRL):
                return True
        return False

    def cleanup(self) -> None:
        """Limpia recursos de la pantalla (superficie y display)."""
        if self._initialized:
            self.clear()
            self.flip()
            pygame.display.quit()
            self._initialized = False
            logger.info("Screen liberado")
