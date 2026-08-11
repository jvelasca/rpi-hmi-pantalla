#!/usr/bin/env python3
"""
fb_ui.py — UI directa sobre framebuffer para Raspberry Pi (ARMv6/v7/v8)

Renderiza panel HMI (botón + LED) directamente en /dev/fb0.
Auto-detecta resolución, profundidad de color y formato de píxel.
Lee touch desde /dev/input/event* (XPT2046/ads7846).
Se comunica con el backend HTTP en localhost:8000.

Sin dependencias externas — solo stdlib de Python 3.9+.

Ejecución:
    sudo python3 fb_ui.py
    sudo python3 fb_ui.py --fb /dev/fb1 --touch /dev/input/event1

Arquitectura:
    fb_ui.py (framebuffer) ←→ pi_hmi_server.py (HTTP :8000 + WS :8001)
                              ↑
                       index.html (navegador)
"""
from __future__ import annotations

import os
import sys
import mmap
import struct
import time
import json
import urllib.request
import argparse
from pathlib import Path


# ═══════════════════════════════════════════════════════════════════════════
# Detección de hardware
# ═══════════════════════════════════════════════════════════════════════════


def detect_fb_params(fb_dev: str) -> dict:
    """Auto-detecta parámetros del framebuffer desde sysfs.

    Lee resolución virtual, bits por píxel y offsets de color
    desde /sys/class/graphics/fb*/.

    Returns:
        dict con keys: width, height, bpp, red_offset, red_length,
        green_offset, green_length, blue_offset, blue_length, alpha_offset,
        alpha_length, stride, size
    """
    # Extraer número de fb desde el nombre del dispositivo
    fb_name = os.path.basename(fb_dev)  # e.g., "fb0"
    sysfs_base = f"/sys/class/graphics/{fb_name}"

    params = {
        "width": 720,
        "height": 480,
        "bpp": 32,
        "red_offset": 16, "red_length": 8,
        "green_offset": 8,  "green_length": 8,
        "blue_offset": 0,   "blue_length": 8,
        "alpha_offset": 24, "alpha_length": 8,
        "stride": 0,
        "size": 0,
    }

    # Leer resolución virtual
    virt_path = os.path.join(sysfs_base, "virtual_size")
    if os.path.exists(virt_path):
        try:
            with open(virt_path) as f:
                w, h = f.read().strip().split(",")
                params["width"] = int(w)
                params["height"] = int(h)
        except (ValueError, OSError):
            pass

    # Leer bits per pixel
    bpp_path = os.path.join(sysfs_base, "bits_per_pixel")
    if os.path.exists(bpp_path):
        try:
            with open(bpp_path) as f:
                params["bpp"] = int(f.read().strip())
        except (ValueError, OSError):
            pass

    # Leer stride (bytes por línea)
    stride_path = os.path.join(sysfs_base, "stride")
    if os.path.exists(stride_path):
        try:
            with open(stride_path) as f:
                params["stride"] = int(f.read().strip())
        except (ValueError, OSError):
            pass

    # Leer offsets de color desde sysfs
    for color in ("red", "green", "blue", "alpha"):
        for attr in ("offset", "length"):
            path = os.path.join(sysfs_base, f"{color}_{attr}")
            if os.path.exists(path):
                try:
                    with open(path) as f:
                        params[f"{color}_{attr}"] = int(f.read().strip())
                except (ValueError, OSError):
                    pass

    # Si no hay stride, calcularlo
    if params["stride"] == 0:
        params["stride"] = params["width"] * (params["bpp"] // 8)

    # Tamaño total del buffer
    params["size"] = params["stride"] * params["height"]

    return params


def find_touch_device() -> str | None:
    """Busca el dispositivo táctil en /dev/input/."""
    candidates = []
    for i in range(10):
        dev = f"/dev/input/event{i}"
        if os.path.exists(dev):
            candidates.append(dev)

    # Buscar el que tenga nombre relacionado con touch/ads7846/xpt
    for dev in candidates:
        name_path = f"/sys/class/input/{os.path.basename(dev)}/device/name"
        if os.path.exists(name_path):
            try:
                with open(name_path) as f:
                    name = f.read().strip().lower()
                    if any(kw in name for kw in ("touch", "ads7846", "xpt", "ft5x", "gt9", "stmpe")):
                        return dev
            except OSError:
                pass

    # Fallback: devolver el último event* encontrado (suele ser event0)
    return candidates[0] if candidates else None


# ═══════════════════════════════════════════════════════════════════════════
# Abstracción de píxel multi-formato
# ═══════════════════════════════════════════════════════════════════════════


class PixelWriter:
    """Escribe píxeles en el framebuffer adaptándose al formato detectado.

    Soporta:
    - 16-bit RGB565 (típico en displays SPI pequeños)
    - 32-bit BGRA/XBGR (framebuffer por software)
    - 24-bit BGR (raro)
    """

    def __init__(self, buf: mmap.mmap, params: dict):
        self.buf = buf
        self.width = params["width"]
        self.height = params["height"]
        self.bpp = params["bpp"]
        self.stride = params["stride"]
        self.bytes_per_pixel = self.bpp // 8
        self._build_packer(params)

    def _build_packer(self, params: dict):
        """Construye la función de empaquetado según el formato."""
        if self.bpp == 16:
            # RGB565 — típico en fbtft
            self.pack = self._pack_rgb565
        elif self.bpp == 24:
            # BGR888
            self.pack = self._pack_bgr888
        else:
            # 32-bit: detectar orden de bytes
            ro = params["red_offset"]
            go = params["green_offset"]
            bo = params["blue_offset"]
            if ro == 16 and bo == 0:
                # Formato BGRA (blue byte 0, green byte 1, red byte 2, alpha byte 3)
                self.pack = self._pack_bgra
            elif ro == 0 and bo == 16:
                # Formato RGBA
                self.pack = self._pack_rgba
            else:
                # Fallback genérico: usar offsets detectados
                self.pack = self._pack_generic

    @staticmethod
    def _pack_rgb565(r: int, g: int, b: int) -> bytes:
        """Empaqueta RGB (0-255) como RGB565 little-endian."""
        val = ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3)
        return struct.pack("<H", val)

    @staticmethod
    def _pack_bgra(r: int, g: int, b: int) -> bytes:
        """Empaqueta como BGRA (formato más común en fbdev 32-bit)."""
        return struct.pack("<I", (0xFF << 24) | (r << 16) | (g << 8) | b)

    @staticmethod
    def _pack_rgba(r: int, g: int, b: int) -> bytes:
        """Empaqueta como RGBA."""
        return struct.pack("<I", (0xFF << 24) | (b << 16) | (g << 8) | r)

    @staticmethod
    def _pack_generic(r: int, g: int, b: int) -> bytes:
        """Empaqueta como BGRA (fallback)."""
        return struct.pack("<I", (0xFF << 24) | (r << 16) | (g << 8) | b)

    @staticmethod
    def _pack_bgr888(r: int, g: int, b: int) -> bytes:
        """Empaqueta como BGR888."""
        return bytes([b, g, r])

    def pixel(self, x: int, y: int, r: int, g: int, b: int):
        """Escribe un píxel en coordenadas (x, y) con color RGB (0-255)."""
        if 0 <= x < self.width and 0 <= y < self.height:
            offset = y * self.stride + x * self.bytes_per_pixel
            self.buf[offset : offset + self.bytes_per_pixel] = self.pack(r, g, b)

    @staticmethod
    def rgb(r: int, g: int, b: int) -> tuple:
        """Devuelve tupla RGB (conveniencia)."""
        return (r, g, b)

    def fill_rect(self, x: int, y: int, w: int, h: int, r: int, g: int, b: int):
        """Rellena un rectángulo con color sólido."""
        x1 = max(0, x)
        y1 = max(0, y)
        x2 = min(self.width, x + w)
        y2 = min(self.height, y + h)
        if x1 >= x2 or y1 >= y2:
            return
        pixel_data = self.pack(r, g, b)
        row_data = pixel_data * (x2 - x1)
        for py in range(y1, y2):
            offset = py * self.stride + x1 * self.bytes_per_pixel
            self.buf[offset : offset + len(row_data)] = row_data

    def draw_rect(self, x: int, y: int, w: int, h: int,
                  r: int, g: int, b: int, thickness: int = 1):
        """Dibuja el borde de un rectángulo."""
        for t in range(thickness):
            self.fill_rect(x + t, y + t, w - 2 * t, 1, r, g, b)
            self.fill_rect(x + t, y + h - 1 - t, w - 2 * t, 1, r, g, b)
            self.fill_rect(x + t, y + t, 1, h - 2 * t, r, g, b)
            self.fill_rect(x + w - 1 - t, y + t, 1, h - 2 * t, r, g, b)

    def draw_circle(self, cx: int, cy: int, radius: int,
                    r: int, g: int, b: int, filled: bool = True):
        """Dibuja un círculo centrado en (cx, cy)."""
        rr = radius * radius
        for dy in range(-radius, radius + 1):
            dx = int((rr - dy * dy) ** 0.5)
            y = cy + dy
            if y < 0 or y >= self.height:
                continue
            if filled:
                for px in range(cx - dx, cx + dx + 1):
                    self.pixel(px, y, r, g, b)
            else:
                self.pixel(cx - dx, y, r, g, b)
                self.pixel(cx + dx, y, r, g, b)


# ═══════════════════════════════════════════════════════════════════════════
# Fuente bitmap 5x7
# ═══════════════════════════════════════════════════════════════════════════

FONT_5X7 = {
    'A': [0x0E, 0x11, 0x11, 0x1F, 0x11, 0x11, 0x11],
    'B': [0x1E, 0x11, 0x11, 0x1E, 0x11, 0x11, 0x1E],
    'C': [0x0E, 0x11, 0x10, 0x10, 0x10, 0x11, 0x0E],
    'D': [0x1E, 0x11, 0x11, 0x11, 0x11, 0x11, 0x1E],
    'E': [0x1F, 0x10, 0x10, 0x1E, 0x10, 0x10, 0x1F],
    'F': [0x1F, 0x10, 0x10, 0x1E, 0x10, 0x10, 0x10],
    'G': [0x0E, 0x11, 0x10, 0x17, 0x11, 0x11, 0x0E],
    'H': [0x11, 0x11, 0x11, 0x1F, 0x11, 0x11, 0x11],
    'I': [0x0E, 0x04, 0x04, 0x04, 0x04, 0x04, 0x0E],
    'J': [0x07, 0x02, 0x02, 0x02, 0x02, 0x12, 0x0C],
    'K': [0x11, 0x12, 0x14, 0x18, 0x14, 0x12, 0x11],
    'L': [0x10, 0x10, 0x10, 0x10, 0x10, 0x10, 0x1F],
    'M': [0x11, 0x1B, 0x15, 0x11, 0x11, 0x11, 0x11],
    'N': [0x11, 0x19, 0x15, 0x13, 0x11, 0x11, 0x11],
    'O': [0x0E, 0x11, 0x11, 0x11, 0x11, 0x11, 0x0E],
    'P': [0x1E, 0x11, 0x11, 0x1E, 0x10, 0x10, 0x10],
    'Q': [0x0E, 0x11, 0x11, 0x11, 0x15, 0x12, 0x0D],
    'R': [0x1E, 0x11, 0x11, 0x1E, 0x14, 0x12, 0x11],
    'S': [0x0E, 0x11, 0x10, 0x0E, 0x01, 0x11, 0x0E],
    'T': [0x1F, 0x04, 0x04, 0x04, 0x04, 0x04, 0x04],
    'U': [0x11, 0x11, 0x11, 0x11, 0x11, 0x11, 0x0E],
    'V': [0x11, 0x11, 0x11, 0x11, 0x11, 0x0A, 0x04],
    'W': [0x11, 0x11, 0x11, 0x15, 0x15, 0x1B, 0x11],
    'X': [0x11, 0x11, 0x0A, 0x04, 0x0A, 0x11, 0x11],
    'Y': [0x11, 0x11, 0x0A, 0x04, 0x04, 0x04, 0x04],
    'Z': [0x1F, 0x01, 0x02, 0x04, 0x08, 0x10, 0x1F],
    '0': [0x0E, 0x11, 0x13, 0x15, 0x19, 0x11, 0x0E],
    '1': [0x04, 0x0C, 0x04, 0x04, 0x04, 0x04, 0x0E],
    '2': [0x0E, 0x11, 0x01, 0x02, 0x04, 0x08, 0x1F],
    '3': [0x0E, 0x11, 0x01, 0x06, 0x01, 0x11, 0x0E],
    '4': [0x02, 0x06, 0x0A, 0x12, 0x1F, 0x02, 0x02],
    '5': [0x1F, 0x10, 0x1E, 0x01, 0x01, 0x11, 0x0E],
    '6': [0x0E, 0x11, 0x10, 0x1E, 0x11, 0x11, 0x0E],
    '7': [0x1F, 0x01, 0x02, 0x04, 0x08, 0x08, 0x08],
    '8': [0x0E, 0x11, 0x11, 0x0E, 0x11, 0x11, 0x0E],
    '9': [0x0E, 0x11, 0x11, 0x0F, 0x01, 0x11, 0x0E],
    ' ': [0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00],
    '.': [0x00, 0x00, 0x00, 0x00, 0x00, 0x0C, 0x0C],
    ':': [0x00, 0x0C, 0x0C, 0x00, 0x0C, 0x0C, 0x00],
    '!': [0x04, 0x04, 0x04, 0x04, 0x00, 0x04, 0x04],
    '/': [0x01, 0x02, 0x02, 0x04, 0x08, 0x08, 0x10],
    '-': [0x00, 0x00, 0x00, 0x1F, 0x00, 0x00, 0x00],
}


def draw_text(pw: PixelWriter, x: int, y: int, text: str,
              r: int, g: int, b: int, scale: int = 1):
    """Dibuja texto con fuente bitmap 5x7 escalable."""
    cx = x
    for ch in text.upper():
        if ch in FONT_5X7:
            bitmap = FONT_5X7[ch]
            for row_idx in range(7):
                row = bitmap[row_idx]
                py = y + row_idx * scale
                for col in range(5):
                    if row & (1 << (4 - col)):
                        px = cx + col * scale
                        for sy in range(scale):
                            for sx in range(scale):
                                pw.pixel(px + sx, py + sy, r, g, b)
        cx += 6 * scale


# ═══════════════════════════════════════════════════════════════════════════
# Panel HMI
# ═══════════════════════════════════════════════════════════════════════════


class HMIPanel:
    """Panel HMI renderizado en framebuffer con soporte táctil."""

    def __init__(self, fb_dev: str = "/dev/fb0", touch_dev: str | None = None,
                 api_base: str = "http://localhost:8000"):
        self.fb_dev = fb_dev
        self.touch_dev = touch_dev
        self.api_base = api_base
        self.running = True
        self.led_state = False
        self.button_pressed = False
        self.press_count = 0
        self.ws_connected = False

        # Handles
        self.fb_fd = None
        self.buf = None
        self.touch_fd = None
        self.pw: PixelWriter | None = None
        self.params: dict = {}

        # Áreas táctiles (se calculan en init_layout)
        self.led_toggle_rect = (0, 0, 0, 0)
        self.button_rect = (0, 0, 0, 0)

    # ── Inicialización ─────────────────────────────────────────────────

    def init(self) -> bool:
        """Inicializa todos los subsistemas. Retorna True si éxito."""
        try:
            self.init_fb()
            self.init_touch()
            self.init_layout()
            return True
        except Exception as e:
            print(f"[FB] Error de inicialización: {e}", file=sys.stderr)
            return False

    def init_fb(self):
        """Inicializa el framebuffer y el PixelWriter."""
        self.fb_fd = os.open(self.fb_dev, os.O_RDWR)
        self.params = detect_fb_params(self.fb_dev)
        self.buf = mmap.mmap(self.fb_fd, self.params["size"],
                             mmap.MAP_SHARED, mmap.PROT_WRITE | mmap.PROT_READ)
        self.pw = PixelWriter(self.buf, self.params)
        print(f"[FB] Framebuffer: {self.params['width']}x{self.params['height']} "
              f"@{self.params['bpp']}bpp ({self.params['size']} bytes)")

    def init_touch(self):
        """Inicializa el dispositivo táctil."""
        if self.touch_dev is None:
            self.touch_dev = find_touch_device()
        if self.touch_dev and os.path.exists(self.touch_dev):
            self.touch_fd = os.open(self.touch_dev, os.O_RDONLY | os.O_NONBLOCK)
            print(f"[FB] Touch: {self.touch_dev}")
        else:
            print("[FB] Touch: no disponible")

    def init_layout(self):
        """Calcula el layout responsive basado en la resolución real."""
        w, h = self.params["width"], self.params["height"]
        # Escalar todo proporcionalmente respecto a 480x320 de referencia
        sx = w / 480.0
        sy = h / 320.0

        # Panel LED (izquierda): 40% del ancho
        led_w = int(180 * sx)
        # Panel Botón (derecha): 40% del ancho
        btn_w = int(180 * sx)
        btn_x = w - btn_w - int(10 * sx)

        margin = int(10 * sy)
        header_h = int(35 * sy)
        footer_h = int(22 * sy)
        content_y = header_h + margin
        content_h = h - header_h - footer_h - margin * 2

        self.led_panel = (int(10 * sx), content_y, led_w, content_h)
        self.btn_panel = (btn_x, content_y, btn_w, content_h)

        # Área del toggle LED (dentro del panel LED)
        self.led_toggle_rect = (
            self.led_panel[0] + int(20 * sx),
            self.led_panel[1] + content_h - int(35 * sy),
            self.led_panel[0] + self.led_panel[2] - int(20 * sx),
            self.led_panel[1] + content_h - int(5 * sy),
        )

        # Área del botón (dentro del panel botón)
        self.button_rect = (
            self.btn_panel[0] + int(10 * sx),
            self.btn_panel[1] + int(10 * sy),
            self.btn_panel[0] + self.btn_panel[2] - int(10 * sx),
            self.btn_panel[1] + self.btn_panel[3] - int(10 * sy),
        )

        # Header/footer
        self.header_rect = (0, 0, w, header_h)
        self.footer_rect = (0, h - footer_h, w, footer_h)

    # ── Dibujo ────────────────────────────────────────────────────────

    def draw_all(self):
        """Redibuja toda la pantalla."""
        pw = self.pw
        w, h = self.params["width"], self.params["height"]

        # Fondo oscuro
        pw.fill_rect(0, 0, w, h, 26, 26, 46)  # #1a1a2e

        # Header
        hr = self.header_rect
        pw.fill_rect(*hr, 22, 33, 62)  # #16213e
        draw_text(pw, hr[0] + 10, hr[1] + 8, "RASPBERRY HMI", 233, 69, 96, 1)  # #e94560
        draw_text(pw, hr[0] + w - 60, hr[1] + 8, "v2.0", 68, 68, 68, 1)

        # Panel LED (izquierda)
        lp = self.led_panel
        pw.fill_rect(*lp, 22, 33, 62)
        pw.draw_rect(*lp, 26, 74, 130, 2)
        draw_text(pw, lp[0] + (lp[2] // 2) - 18, lp[1] + 8, "LED 1", 192, 192, 192, 1)

        # Círculo LED
        led_cx = lp[0] + lp[2] // 2
        led_cy = lp[1] + lp[3] // 2 - 15
        led_r = min(lp[2], lp[3]) // 4
        if self.led_state:
            pw.draw_circle(led_cx, led_cy, led_r + 8, 40, 0, 0, True)
            pw.draw_circle(led_cx, led_cy, led_r + 3, 120, 0, 0, True)
            pw.draw_circle(led_cx, led_cy, led_r, 248, 0, 0, True)
            pw.draw_circle(led_cx, led_cy, led_r - 3, 255, 40, 40, True)
            pw.draw_circle(led_cx - led_r // 3, led_cy - led_r // 3,
                           led_r // 4, 255, 150, 120, True)
            draw_text(pw, lp[0] + (lp[2] // 2) - 30, led_cy + led_r + 10,
                      "ENCENDIDO", 255, 80, 80, 1)
        else:
            pw.draw_circle(led_cx, led_cy, led_r, 68, 68, 68, True)
            pw.draw_circle(led_cx, led_cy, led_r - 2, 100, 100, 100, True)
            pw.draw_circle(led_cx - led_r // 3, led_cy - led_r // 3,
                           led_r // 4, 130, 130, 130, True)
            draw_text(pw, lp[0] + (lp[2] // 2) - 24, led_cy + led_r + 10,
                      "APAGADO", 102, 102, 102, 1)

        # Toggle LED button
        tr = self.led_toggle_rect
        pw.fill_rect(*tr, 15, 52, 96)
        pw.draw_rect(*tr, 0, 31, 160, 1)
        label = "APAGAR" if self.led_state else "ENCENDER"
        lx = tr[0] + (tr[2] - tr[0]) // 2 - len(label) * 3
        draw_text(pw, lx, tr[1] + (tr[3] - tr[1]) // 2 - 4, label, 255, 255, 255, 1)

        # Panel Botón (derecha)
        bp = self.btn_panel
        pw.fill_rect(*bp, 22, 33, 62)
        pw.draw_rect(*bp, 26, 74, 130, 2)
        draw_text(pw, bp[0] + (bp[2] // 2) - 18, bp[1] + 8, "BOTON", 192, 192, 192, 1)

        btn_cx = bp[0] + bp[2] // 2
        btn_cy = bp[1] + bp[3] // 2 - 15
        btn_r = min(bp[2], bp[3]) // 4 + 5
        if self.button_pressed:
            pw.draw_circle(btn_cx, btn_cy, btn_r, 0, 50, 0, True)
            pw.draw_circle(btn_cx, btn_cy, btn_r - 3, 0, 200, 80, True)
            draw_text(pw, bp[0] + (bp[2] // 2) - 22, btn_cy - 4, "PULSADO", 255, 255, 255, 1)
        else:
            pw.draw_circle(btn_cx, btn_cy, btn_r, 15, 52, 96, True)
            pw.draw_circle(btn_cx, btn_cy, btn_r - 3, 30, 80, 140, True)
            draw_text(pw, bp[0] + (bp[2] // 2) - 18, btn_cy - 4, "PULSAR", 255, 255, 255, 1)

        # Contador de pulsaciones
        count_y = btn_cy + btn_r + 10
        draw_text(pw, bp[0] + (bp[2] // 2) - 36, count_y, "Pulsaciones:", 136, 136, 136, 1)
        count_text = str(self.press_count)
        ctw = len(count_text) * 6
        draw_text(pw, bp[0] + (bp[2] // 2) - ctw // 2, count_y + 12,
                  count_text, 233, 69, 96, 2)

        # Footer
        fr = self.footer_rect
        pw.fill_rect(*fr, 0, 0, 0)
        t = time.strftime("%H:%M:%S")
        draw_text(pw, fr[0] + 10, fr[1] + 4, t, 68, 68, 68, 1)
        status = "WS:OK" if self.ws_connected else "WS:--"
        draw_text(pw, fr[0] + fr[2] - 80, fr[1] + 4, status, 68, 68, 68, 1)

    # ── Touch ─────────────────────────────────────────────────────────

    def read_touch(self) -> tuple | None:
        """Lee un evento táctil crudo. Retorna (type, code, value) o None."""
        if self.touch_fd is None:
            return None
        try:
            data = os.read(self.touch_fd, 16)
            if len(data) == 16:
                sec, usec, ev_type, ev_code, ev_value = (
                    struct.unpack('<llHHi', data))
                return (ev_type, ev_code, ev_value)
        except (BlockingIOError, OSError):
            pass
        return None

    def _touch_to_screen(self, raw_x: int, raw_y: int) -> tuple:
        """Convierte coordenadas táctiles crudas a coordenadas de pantalla.

        Asume rotate=270 (el overlay ads7846 está configurado así).
        XPT2046 raw: 0-4095. Screen: width x height.
        """
        w, h = self.params["width"], self.params["height"]
        # Con rotate=270: la coordenada X cruda mapea a Y invertido de pantalla
        screen_y = h - 1 - int(raw_x * h / 4096)
        screen_x = int(raw_y * w / 4096)
        return (screen_x, screen_y)

    def process_touch(self, screen_x: int, screen_y: int):
        """Procesa un toque en coordenadas de pantalla."""
        # Toggle LED
        tr = self.led_toggle_rect
        if tr[0] <= screen_x <= tr[2] and tr[1] <= screen_y <= tr[3]:
            self._api_toggle_led()
            self.draw_all()
            time.sleep(0.15)
            return

        # Botón principal
        br = self.button_rect
        if br[0] <= screen_x <= br[2] and br[1] <= screen_y <= br[3]:
            self._api_press_button()
            self.button_pressed = True
            self.draw_all()
            time.sleep(0.15)
            self.button_pressed = False
            self.draw_all()

    # ── API ───────────────────────────────────────────────────────────

    def _api_call(self, endpoint: str, method: str = "GET") -> dict | None:
        """Llama a un endpoint de la API REST."""
        try:
            req = urllib.request.Request(f"{self.api_base}{endpoint}", method=method)
            with urllib.request.urlopen(req, timeout=2) as resp:
                return json.loads(resp.read())
        except Exception:
            return None

    def _api_toggle_led(self):
        """Alterna el LED vía API."""
        data = self._api_call("/api/led/toggle", "POST")
        if data:
            self.led_state = data.get("state", self.led_state)
            print(f"[HMI] LED: {'ON' if self.led_state else 'OFF'}")
        else:
            # Toggle local si API no disponible
            self.led_state = not self.led_state

    def _api_press_button(self):
        """Registra pulsación de botón vía API."""
        data = self._api_call("/api/button/press", "POST")
        if data:
            self.press_count = data.get("press_count", self.press_count)
            print(f"[HMI] Botón: {self.press_count}")
        else:
            self.press_count += 1

    def sync_status(self):
        """Sincroniza estado con el backend."""
        data = self._api_call("/api/status")
        if data:
            self.led_state = data.get("led", {}).get("state", self.led_state)
            self.press_count = data.get("button", {}).get("press_count", self.press_count)
            self.ws_connected = data.get("websocket_clients", 0) > 0

    # ── Bucle principal ───────────────────────────────────────────────

    def run(self):
        """Bucle principal de la UI."""
        if self.pw is None:
            print("[FB] ERROR: Framebuffer no inicializado", file=sys.stderr)
            return

        self.sync_status()
        self.draw_all()

        touch_x = touch_y = touch_pressure = 0
        touch_active = False
        last_sync = time.time()
        last_draw = last_sync
        sync_interval = 1.0     # Sincronizar estado cada 1s
        draw_interval = 0.5     # Redibujar como máximo cada 500ms

        print("[FB] Panel HMI iniciado — Ctrl+C para salir")

        while self.running:
            try:
                dirty = False

                # Leer eventos táctiles
                while True:
                    ev = self.read_touch()
                    if ev is None:
                        break
                    ev_type, ev_code, ev_value = ev

                    if ev_type == 3:  # EV_ABS
                        if ev_code == 0:
                            touch_x = ev_value
                        elif ev_code == 1:
                            touch_y = ev_value
                        elif ev_code == 24:
                            touch_pressure = ev_value

                    elif ev_type == 0 and ev_code == 0:  # SYN_REPORT
                        if touch_pressure > 100 and not touch_active:
                            touch_active = True
                            sx, sy = self._touch_to_screen(touch_x, touch_y)
                            self.process_touch(sx, sy)
                            dirty = True
                        elif touch_pressure < 50 and touch_active:
                            touch_active = False

                # Sincronizar estado periódicamente
                now = time.time()
                if now - last_sync > sync_interval:
                    old_led = self.led_state
                    old_count = self.press_count
                    self.sync_status()
                    if old_led != self.led_state or old_count != self.press_count:
                        dirty = True
                    last_sync = now

                # Redibujar si es necesario (con rate limiting)
                if dirty and now - last_draw > draw_interval:
                    self.draw_all()
                    last_draw = now

                time.sleep(0.02)  # 50Hz — suficiente para touch, bajo CPU

            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"[FB] Error en bucle: {e}", file=sys.stderr)
                time.sleep(0.5)

        self.cleanup()

    def cleanup(self):
        """Libera todos los recursos."""
        if self.pw:
            self.pw.fill_rect(0, 0, self.params["width"], self.params["height"], 0, 0, 0)
        if self.buf:
            self.buf.close()
        if self.fb_fd is not None:
            os.close(self.fb_fd)
        if self.touch_fd is not None:
            os.close(self.touch_fd)
        print("[FB] Panel cerrado")


# ═══════════════════════════════════════════════════════════════════════════
# Punto de entrada
# ═══════════════════════════════════════════════════════════════════════════


def main():
    parser = argparse.ArgumentParser(
        description="Panel HMI directo sobre framebuffer para Raspberry Pi",
    )
    parser.add_argument("--fb", default="/dev/fb0", help="Dispositivo framebuffer")
    parser.add_argument("--touch", default=None, help="Dispositivo táctil (auto-detecta si no se especifica)")
    parser.add_argument("--api", default="http://localhost:8000", help="URL base de la API REST")
    args = parser.parse_args()

    print("=" * 50)
    print("  Raspberry Pi HMI — Framebuffer Panel v2.0")
    print("=" * 50)

    panel = HMIPanel(fb_dev=args.fb, touch_dev=args.touch, api_base=args.api)
    if panel.init():
        panel.run()
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
