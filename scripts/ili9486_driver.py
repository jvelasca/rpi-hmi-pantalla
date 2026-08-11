#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ili9486_driver.py — Driver Python puro para pantalla ILI9486 480x320 por SPI

Usa spidev para comunicacion SPI y GPIO sysfs para DC y RESET.
No depende del driver fbtft del kernel (que esta roto en kernel 6.12).

Conexionado:
    SPI0 MOSI (GPIO10) — SDA/MOSI de la pantalla
    SPI0 SCLK (GPIO11) — SCLK de la pantalla
    SPI0 CE0  (GPIO8)  — CS de la pantalla
    GPIO 24            — DC (Data/Command)
    GPIO 17            — RESET
    GPIO 18            — LED (backlight)

Uso:
    sudo python3 ili9486_driver.py          # Test: rellena pantalla de rojo
    sudo python3 ili9486_driver.py --run    # Bucle HMI completo
"""

import os
import sys
import time
import struct
import argparse

# ── Configuracion de pines ──────────────────────────────────
PIN_DC = 24
PIN_RST = 17
PIN_LED = 18

# Dimensiones de pantalla
WIDTH = 480
HEIGHT = 320

# Inicializacion ILI9486 (registros de configuracion)
# Secuencia estandar para ILI9486 en modo SPI 4-wire
ILI9486_INIT = [
    # (command, [data bytes], delay_ms)
    (0x01, [], 150),          # Software reset
    (0x11, [], 255),          # Sleep out
    (0x3A, [0x55], 10),      # Interface pixel format: 16bpp RGB565
    (0x36, [0x28], 10),      # Memory access control: BGR, landscape
    (0xC2, [0x44], 10),      # Power Control 3
    (0xC5, [0x00, 0x00, 0x00, 0x00], 10),  # VCOM Control
    (0xE0, [0x0F, 0x1F, 0x1C, 0x0C, 0x0F, 0x08, 0x48, 0x98,
             0x37, 0x0A, 0x13, 0x04, 0x11, 0x0D, 0x00], 10),  # PGAMCTRL
    (0xE1, [0x0F, 0x32, 0x2E, 0x0B, 0x0D, 0x05, 0x47, 0x75,
             0x37, 0x06, 0x10, 0x03, 0x24, 0x20, 0x00], 10),  # NGAMCTRL
    (0x20, [], 10),           # Display Inversion OFF
    (0x13, [], 10),           # Normal Display Mode ON
    (0x29, [], 255),          # Display ON
]


class ILI9486:
    """Driver para pantalla ILI9486 480x320 por SPI."""

    def __init__(self, bus=0, device=0, dc=PIN_DC, rst=PIN_RST, led=PIN_LED):
        self.spi = None
        self.width = WIDTH
        self.height = HEIGHT
        self.dc = dc
        self.rst = rst
        self.led = led
        self.bus = bus
        self.cs = device
        self._dc_path = f"/sys/class/gpio/gpio{dc}/value"
        self._rst_path = f"/sys/class/gpio/gpio{rst}/value"
        self._led_path = f"/sys/class/gpio/gpio{led}/value"

    def _export_gpio(self, pin, direction="out"):
        """Exporta un GPIO via sysfs."""
        gpio_path = f"/sys/class/gpio/gpio{pin}"
        if not os.path.exists(gpio_path):
            try:
                with open("/sys/class/gpio/export", "w") as f:
                    f.write(str(pin))
                time.sleep(0.05)
            except OSError:
                pass  # Ya puede estar exportado
        if os.path.exists(gpio_path):
            try:
                with open(f"{gpio_path}/direction", "w") as f:
                    f.write(direction)
            except OSError:
                pass

    def _write_gpio(self, pin, value):
        """Escribe valor a GPIO via sysfs."""
        path = f"/sys/class/gpio/gpio{pin}/value"
        try:
            with open(path, "w") as f:
                f.write("1" if value else "0")
        except OSError:
            pass

    def init_gpio(self):
        """Inicializa los GPIOs."""
        self._export_gpio(self.dc, "out")
        self._export_gpio(self.rst, "out")
        self._export_gpio(self.led, "out")
        self._write_gpio(self.led, 1)  # Backlight ON
        time.sleep(0.05)

    def reset(self):
        """Hardware reset de la pantalla."""
        self._write_gpio(self.rst, 1)
        time.sleep(0.01)
        self._write_gpio(self.rst, 0)
        time.sleep(0.01)
        self._write_gpio(self.rst, 1)
        time.sleep(0.12)

    def init_spi(self):
        """Inicializa el bus SPI."""
        spidev_path = f"/dev/spidev{self.bus}.{self.cs}"
        if not os.path.exists(spidev_path):
            # Intentar con nombres alternativos
            alt = f"/dev/spidev{self.bus}_{self.cs}"
            if os.path.exists(alt):
                spidev_path = alt
            else:
                raise RuntimeError(
                    f"SPI device {spidev_path} no encontrado. "
                    f"Asegurate de que dtparam=spi=on esta en /boot/config.txt"
                )
        self.spi = open(spidev_path, "wb", buffering=0)
        print(f"[ILI9486] SPI abierto: {spidev_path}")

    def send_cmd(self, cmd, data=None):
        """Envia un comando seguido de datos opcionales a la pantalla."""
        # DC = 0 para comando
        self._write_gpio(self.dc, 0)
        self.spi.write(bytes([cmd]))
        time.sleep(0.00001)

        # DC = 1 para datos
        if data:
            self._write_gpio(self.dc, 1)
            self.spi.write(bytes(data))

    def init_display(self):
        """Inicializa la pantalla con la secuencia de configuracion."""
        for cmd, data, delay in ILI9486_INIT:
            self.send_cmd(cmd, data)
            time.sleep(delay / 1000.0)
        print("[ILI9486] Display inicializado")

    def set_window(self, x0=0, y0=0, x1=None, y1=None):
        """Define la ventana de dibujo (column/row address)."""
        if x1 is None:
            x1 = self.width - 1
        if y1 is None:
            y1 = self.height - 1

        # Column address
        self.send_cmd(0x2A, [
            (x0 >> 8) & 0xFF, x0 & 0xFF,
            (x1 >> 8) & 0xFF, x1 & 0xFF,
        ])
        # Row address
        self.send_cmd(0x2B, [
            (y0 >> 8) & 0xFF, y0 & 0xFF,
            (y1 >> 8) & 0xFF, y1 & 0xFF,
        ])
        # Memory write
        self.send_cmd(0x2C)

    def fill_screen(self, color_rgb565):
        """Rellena toda la pantalla con un color RGB565."""
        hi = (color_rgb565 >> 8) & 0xFF
        lo = color_rgb565 & 0xFF
        self.set_window()
        self._write_gpio(self.dc, 1)
        pixel_row = bytes([hi, lo]) * self.width
        for _ in range(self.height):
            self.spi.write(pixel_row)
        print(f"[ILI9486] Pantalla rellena: 0x{color_rgb565:04X}")

    def fill_rect(self, x, y, w, h, color_rgb565):
        """Rellena un rectangulo."""
        hi = (color_rgb565 >> 8) & 0xFF
        lo = color_rgb565 & 0xFF
        self.set_window(x, y, x + w - 1, y + h - 1)
        self._write_gpio(self.dc, 1)
        pixel_row = bytes([hi, lo]) * w
        for _ in range(h):
            self.spi.write(pixel_row)

    def close(self):
        """Cierra la conexion SPI."""
        if self.spi:
            self.spi.close()

    def __enter__(self):
        self.init_gpio()
        self.reset()
        self.init_spi()
        self.init_display()
        return self

    def __exit__(self, *args):
        self.close()


def rgb_to_565(r, g, b):
    """Convierte RGB (0-255) a RGB565."""
    return ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3)


# ── Colores ─────────────────────────────────────────────────
WHITE = rgb_to_565(255, 255, 255)
BLACK = rgb_to_565(0, 0, 0)
RED = rgb_to_565(255, 0, 0)
GREEN = rgb_to_565(0, 255, 0)
BLUE = rgb_to_565(0, 0, 255)
DARK_BG = rgb_to_565(26, 26, 46)    # #1a1a2e
PANEL_BG = rgb_to_565(22, 33, 62)   # #16213e
ACCENT = rgb_to_565(233, 69, 96)    # #e94560
GRAY = rgb_to_565(68, 68, 68)
LIGHT_GRAY = rgb_to_565(192, 192, 192)
BTN_GREEN = rgb_to_565(15, 52, 96)  # #0f3460


def test_pattern():
    """Test rapido: rayas de colores en la pantalla."""
    print("=" * 50)
    print("  ILI9486 DRIVER TEST")
    print("=" * 50)

    try:
        with ILI9486() as lcd:
            print("\n[*] Relleno de negro...")
            lcd.fill_screen(BLACK)
            time.sleep(0.5)

            print("[*] Relleno de rojo...")
            lcd.fill_screen(RED)
            time.sleep(1)

            print("[*] Relleno de verde...")
            lcd.fill_screen(GREEN)
            time.sleep(1)

            print("[*] Relleno de azul...")
            lcd.fill_screen(BLUE)
            time.sleep(1)

            print("[*] Relleno de blanco...")
            lcd.fill_screen(WHITE)
            time.sleep(1)

            print("[*] Relleno de negro...")
            lcd.fill_screen(BLACK)
            time.sleep(0.5)

            # Patron HMI sencillo
            print("[*] Dibujando UI HMI...")
            lcd.fill_screen(DARK_BG)

            # Header
            lcd.fill_rect(0, 0, lcd.width, 35, PANEL_BG)

            # Panel LED (izquierda)
            lcd.fill_rect(10, 45, 180, 240, PANEL_BG)

            # Panel Boton (derecha)
            lcd.fill_rect(290, 45, 180, 240, PANEL_BG)

            # Circulo rojo (LED simulado)
            lcd.fill_rect(100, 110, 80, 80, RED)

            # Circulo azul (boton simulado)
            lcd.fill_rect(380, 110, 80, 80, BTN_GREEN)

            print("[OK] Patron HMI dibujado. La pantalla deberia mostrar la UI.")

            print("\nPresiona Ctrl+C para salir...")
            while True:
                time.sleep(1)

    except KeyboardInterrupt:
        print("\n[*] Saliendo...")
    except RuntimeError as e:
        print(f"\n[ERROR] {e}")
        print("\nVerifica que /dev/spidev0.0 existe:")
        print("  sudo raspi-config -> Interface Options -> SPI -> Enable")
        print("  sudo reboot")
        return 1
    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ILI9486 Python Driver Test")
    parser.add_argument("--bus", type=int, default=0, help="SPI bus (default: 0)")
    parser.add_argument("--cs", type=int, default=0, help="SPI chip select (default: 0)")
    args = parser.parse_args()

    # Actualizar defaults
    ILI9486.__init__.__defaults__ = (args.bus, args.cs, PIN_DC, PIN_RST, PIN_LED)

    sys.exit(test_pattern())
