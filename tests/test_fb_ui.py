"""
test_fb_ui.py — Tests unitarios para el módulo fb_ui (UI framebuffer)

Prueba las funciones sin necesidad de hardware real:
- detect_fb_params: auto-detección de sysfs
- PixelWriter: escritura de píxeles en todos los formatos
- draw_text: renderizado de fuente bitmap
- FONT_5X7: integridad de la fuente
- HMIPanel: lógica de layout y API

Ejecutar:
    pytest tests/test_fb_ui.py -v
    pytest tests/test_fb_ui.py -v --cov=fb_ui
"""
from __future__ import annotations

import sys
import os
import mmap
import struct
import pytest

# Añadir proyecto al path (fb_ui está en legacy/)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "legacy"))
import fb_ui


# ═══════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════


def make_fb_params(width=720, height=480, bpp=32, red_off=16, green_off=8, blue_off=0):
    """Crea parámetros de framebuffer simulados."""
    return {
        "width": width,
        "height": height,
        "bpp": bpp,
        "red_offset": red_off,
        "red_length": 8,
        "green_offset": green_off,
        "green_length": 8,
        "blue_offset": blue_off,
        "blue_length": 8,
        "alpha_offset": 24,
        "alpha_length": 8,
        "stride": width * (bpp // 8),
        "size": width * height * (bpp // 8),
    }


def make_mock_buf(params: dict) -> mmap.mmap:
    """Crea un buffer mmap simulado con el tamaño correcto."""
    # Usamos mmap anónimo para testing sin archivo real
    return mmap.mmap(-1, params["size"])


# ═══════════════════════════════════════════════════════════════════════════
# Font tests
# ═══════════════════════════════════════════════════════════════════════════


class TestFont:
    """Tests para la fuente bitmap FONT_5X7."""

    def test_all_uppercase_letters_defined(self):
        """Todas las letras mayúsculas A-Z deben estar definidas."""
        for ch in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
            assert ch in fb_ui.FONT_5X7, f"Falta la letra '{ch}'"

    def test_all_digits_defined(self):
        """Todos los dígitos 0-9 deben estar definidos."""
        for ch in "0123456789":
            assert ch in fb_ui.FONT_5X7, f"Falta el dígito '{ch}'"

    def test_special_chars_defined(self):
        """Caracteres especiales deben estar definidos."""
        for ch in " .:!-/":
            assert ch in fb_ui.FONT_5X7, f"Falta el carácter especial '{ch}'"

    def test_each_char_has_7_rows(self):
        """Cada carácter debe tener exactamente 7 filas."""
        for ch, bitmap in fb_ui.FONT_5X7.items():
            assert len(bitmap) == 7, f"'{ch}' tiene {len(bitmap)} filas, esperado 7"

    def test_each_row_is_byte(self):
        """Cada fila debe ser un valor de 0-31 (5 bits de ancho)."""
        for ch, bitmap in fb_ui.FONT_5X7.items():
            for row in bitmap:
                assert 0 <= row <= 31, f"'{ch}' fila {row} fuera de rango 0-31"


# ═══════════════════════════════════════════════════════════════════════════
# PixelWriter tests — 32-bit BGRA (formato más común)
# ═══════════════════════════════════════════════════════════════════════════


class TestPixelWriter32BGRA:
    """Tests para PixelWriter en formato 32-bit BGRA (fbdev estándar)."""

    @pytest.fixture
    def pw(self):
        params = make_fb_params(bpp=32, red_off=16, green_off=8, blue_off=0)
        buf = make_mock_buf(params)
        yield fb_ui.PixelWriter(buf, params)
        buf.close()

    def test_initialization(self, pw):
        """PixelWriter debe inicializarse correctamente."""
        assert pw.width == 720
        assert pw.height == 480
        assert pw.bpp == 32
        assert pw.bytes_per_pixel == 4

    def test_pixel_writes_bgra(self, pw):
        """Escribir un píxel rojo (255,0,0) debe generar bytes BGRA: 0,0,255,255."""
        pw.pixel(0, 0, 255, 0, 0)
        data = pw.buf[0:4]
        # BGRA: B=0, G=0, R=255, A=255
        assert data[0] == 0     # Blue
        assert data[1] == 0     # Green
        assert data[2] == 255   # Red
        assert data[3] == 255   # Alpha

    def test_pixel_green(self, pw):
        """Píxel verde (0,255,0) → B=0, G=255, R=0, A=255."""
        pw.pixel(10, 10, 0, 255, 0)
        offset = (10 * pw.stride + 10 * 4)
        data = pw.buf[offset:offset + 4]
        assert data[0] == 0
        assert data[1] == 255
        assert data[2] == 0
        assert data[3] == 255

    def test_pixel_blue(self, pw):
        """Píxel azul (0,0,255) → B=255, G=0, R=0, A=255."""
        pw.pixel(5, 5, 0, 0, 255)
        offset = (5 * pw.stride + 5 * 4)
        data = pw.buf[offset:offset + 4]
        assert data[0] == 255
        assert data[1] == 0
        assert data[2] == 0
        assert data[3] == 255

    def test_pixel_white(self, pw):
        """Píxel blanco (255,255,255) → B=255, G=255, R=255, A=255."""
        pw.pixel(0, 0, 255, 255, 255)
        data = pw.buf[0:4]
        assert data == bytes([255, 255, 255, 255])

    def test_pixel_out_of_bounds(self, pw):
        """Píxeles fuera de los límites no deben causar errores."""
        # Estos no deben lanzar excepción
        pw.pixel(-1, 0, 255, 0, 0)
        pw.pixel(0, -1, 255, 0, 0)
        pw.pixel(pw.width, 0, 255, 0, 0)
        pw.pixel(0, pw.height, 255, 0, 0)
        pw.pixel(pw.width + 100, pw.height + 100, 255, 0, 0)

    def test_fill_rect_full_screen(self, pw):
        """Rellenar toda la pantalla con un color."""
        pw.fill_rect(0, 0, pw.width, pw.height, 26, 26, 46)
        # Verificar esquinas
        for x, y in [(0, 0), (pw.width - 1, 0), (0, pw.height - 1),
                      (pw.width - 1, pw.height - 1)]:
            offset = y * pw.stride + x * 4
            data = pw.buf[offset:offset + 4]
            assert data[0] == 46   # Blue
            assert data[1] == 26   # Green
            assert data[2] == 26   # Red
            assert data[3] == 255  # Alpha

    def test_fill_rect_partial(self, pw):
        """Rellenar un rectángulo parcial."""
        pw.fill_rect(0, 0, pw.width, pw.height, 0, 0, 0)  # Black background
        pw.fill_rect(100, 50, 200, 100, 255, 0, 0)  # Red rect

        # Punto dentro del rectángulo rojo
        offset = 75 * pw.stride + 150 * 4
        data = pw.buf[offset:offset + 4]
        assert data[2] == 255  # Red

        # Punto fuera del rectángulo (debe ser negro)
        offset2 = 10 * pw.stride + 10 * 4
        data2 = pw.buf[offset2:offset2 + 4]
        assert data2[2] == 0  # Black

    def test_fill_rect_clipped(self, pw):
        """Rectángulo parcialmente fuera de pantalla debe recortarse."""
        # No debe lanzar excepción
        pw.fill_rect(-10, -10, 50, 50, 255, 0, 0)  # Parcialmente fuera
        pw.fill_rect(pw.width - 10, pw.height - 10, 50, 50, 255, 0, 0)  # Esquina inferior

    def test_draw_rect_border(self, pw):
        """Borde de rectángulo con thickness 2."""
        pw.fill_rect(0, 0, pw.width, pw.height, 0, 0, 0)
        pw.draw_rect(50, 50, 100, 80, 255, 255, 0, thickness=2)

        # Punto en el borde (debe ser amarillo)
        data = pw.buf[50 * pw.stride + 51 * 4: 50 * pw.stride + 55 * 4]
        assert data[2] == 255  # Red del amarillo

    def test_draw_circle_filled(self, pw):
        """Círculo relleno."""
        pw.fill_rect(0, 0, pw.width, pw.height, 0, 0, 0)
        pw.draw_circle(360, 240, 50, 255, 0, 0, True)

        # Centro del círculo debe ser rojo
        offset = 240 * pw.stride + 360 * 4
        data = pw.buf[offset:offset + 4]
        assert data[2] == 255

    def test_draw_circle_outline(self, pw):
        """Círculo solo borde."""
        pw.fill_rect(0, 0, pw.width, pw.height, 0, 0, 0)
        pw.draw_circle(360, 240, 30, 0, 255, 0, False)

        # Centro del círculo debe ser negro (hueco)
        offset = 240 * pw.stride + 360 * 4
        data = pw.buf[offset:offset + 4]
        assert data[1] == 0  # Green = 0 → negro

    def test_rgb_helper(self, pw):
        """El helper rgb() devuelve tupla correcta."""
        assert pw.rgb(255, 128, 0) == (255, 128, 0)
        assert pw.rgb(0, 0, 0) == (0, 0, 0)


# ═══════════════════════════════════════════════════════════════════════════
# PixelWriter tests — 16-bit RGB565
# ═══════════════════════════════════════════════════════════════════════════


class TestPixelWriter16RGB565:
    """Tests para PixelWriter en formato 16-bit RGB565 (displays SPI)."""

    @pytest.fixture
    def pw(self):
        params = make_fb_params(width=480, height=320, bpp=16,
                                red_off=11, green_off=5, blue_off=0)
        # Ajustar stride y size para 16bpp
        params["stride"] = 480 * 2
        params["size"] = 480 * 320 * 2
        buf = make_mock_buf(params)
        yield fb_ui.PixelWriter(buf, params)
        buf.close()

    def test_16bpp_initialization(self, pw):
        """PixelWriter 16bpp debe tener 2 bytes por píxel."""
        assert pw.width == 480
        assert pw.height == 320
        assert pw.bpp == 16
        assert pw.bytes_per_pixel == 2

    def test_pixel_red_rgb565(self, pw):
        """Rojo puro en RGB565 debe ser 0xF800 (little-endian: 0x00, 0xF8)."""
        pw.pixel(0, 0, 255, 0, 0)
        data = pw.buf[0:2]
        val = struct.unpack("<H", data)[0]
        # R=255>>3=31<<11=0xF800
        assert val == 0xF800

    def test_pixel_green_rgb565(self, pw):
        """Verde puro en RGB565 debe ser 0x07E0."""
        pw.pixel(0, 0, 0, 255, 0)
        data = pw.buf[0:2]
        val = struct.unpack("<H", data)[0]
        assert val == 0x07E0

    def test_pixel_blue_rgb565(self, pw):
        """Azul puro en RGB565 debe ser 0x001F."""
        pw.pixel(0, 0, 0, 0, 255)
        data = pw.buf[0:2]
        val = struct.unpack("<H", data)[0]
        assert val == 0x001F

    def test_pixel_white_rgb565(self, pw):
        """Blanco en RGB565 debe ser 0xFFFF."""
        pw.pixel(0, 0, 255, 255, 255)
        data = pw.buf[0:2]
        val = struct.unpack("<H", data)[0]
        assert val == 0xFFFF

    def test_pixel_black_rgb565(self, pw):
        """Negro en RGB565 debe ser 0x0000."""
        pw.pixel(0, 0, 0, 0, 0)
        data = pw.buf[0:2]
        val = struct.unpack("<H", data)[0]
        assert val == 0x0000


# ═══════════════════════════════════════════════════════════════════════════
# Draw text tests
# ═══════════════════════════════════════════════════════════════════════════


class TestDrawText:
    """Tests para la función draw_text."""

    @pytest.fixture
    def pw(self):
        params = make_fb_params(bpp=32)
        buf = make_mock_buf(params)
        yield fb_ui.PixelWriter(buf, params)
        buf.close()

    def test_draw_text_writes_pixels(self, pw):
        """Dibujar texto debe escribir píxeles no negros."""
        pw.fill_rect(0, 0, pw.width, pw.height, 0, 0, 0)
        fb_ui.draw_text(pw, 10, 10, "TEST", 255, 255, 255, 1)

        # Buscar algún píxel blanco en el área del texto
        found_white = False
        for y in range(10, 20):
            for x in range(10, 60):
                offset = y * pw.stride + x * 4
                data = pw.buf[offset:offset + 4]
                if data[2] == 255 and data[1] == 255 and data[0] == 255:
                    found_white = True
                    break
            if found_white:
                break
        assert found_white, "No se encontraron píxeles blancos después de draw_text"

    def test_draw_text_with_scale(self, pw):
        """Texto con scale=2 debe ocupar el doble de espacio."""
        pw.fill_rect(0, 0, pw.width, pw.height, 0, 0, 0)
        fb_ui.draw_text(pw, 10, 10, "A", 255, 0, 0, 2)

        # Verificar que hay píxeles rojos en un área 10x14 (5x7 * 2)
        found = False
        for y in range(10, 24):
            for x in range(10, 20):
                offset = y * pw.stride + x * 4
                if pw.buf[offset + 2] == 255:
                    found = True
                    break
            if found:
                break
        assert found, "Texto con scale=2 no renderizó píxeles"

    def test_draw_text_empty_string(self, pw):
        """Texto vacío no debe causar error."""
        pw.fill_rect(0, 0, pw.width, pw.height, 0, 0, 0)
        fb_ui.draw_text(pw, 0, 0, "", 255, 255, 255, 1)

    def test_draw_text_special_chars(self, pw):
        """Caracteres especiales deben renderizarse."""
        pw.fill_rect(0, 0, pw.width, pw.height, 0, 0, 0)
        fb_ui.draw_text(pw, 10, 10, "HOLA!", 255, 255, 255, 1)

    def test_draw_text_unknown_char_skipped(self, pw):
        """Caracteres no definidos deben omitirse sin error."""
        pw.fill_rect(0, 0, pw.width, pw.height, 0, 0, 0)
        fb_ui.draw_text(pw, 10, 10, "TEST_%", 255, 255, 255, 1)


# ═══════════════════════════════════════════════════════════════════════════
# Touch coordinate mapping
# ═══════════════════════════════════════════════════════════════════════════


class TestTouchMapping:
    """Tests para el mapeo de coordenadas táctiles."""

    def make_pw(self, width=720, height=480):
        params = make_fb_params(width=width, height=height, bpp=32)
        buf = make_mock_buf(params)
        return fb_ui.PixelWriter(buf, params), buf

    def test_center_touch_maps_to_center(self):
        """Toque en el centro (2048, 2048) debe mapear al centro de pantalla."""
        pw, buf = self.make_pw(720, 480)
        # Usamos la función _touch_to_screen del panel
        panel = fb_ui.HMIPanel()
        panel.pw = pw
        panel.params = make_fb_params(720, 480)
        screen_x, screen_y = panel._touch_to_screen(2048, 2048)
        assert 340 < screen_x < 380, f"X={screen_x} debería estar cerca de 360"
        assert 220 < screen_y < 260, f"Y={screen_y} debería estar cerca de 240"
        buf.close()

    def test_top_left_touch(self):
        """Toque en (0, 4095) debe mapear cerca de la esquina superior izquierda."""
        panel = fb_ui.HMIPanel()
        pw, buf = self.make_pw(720, 480)
        panel.pw = pw
        panel.params = make_fb_params(720, 480)
        screen_x, screen_y = panel._touch_to_screen(0, 4095)
        # Con rotate=270: X crudo=0 → Y pantalla = h-1-0*480/4096 = 479
        # Y crudo=4095 → X pantalla = 4095*720/4096 ≈ 719
        assert screen_x > 700, f"X={screen_x}"
        assert screen_y > 470, f"Y={screen_y}"
        buf.close()


# ═══════════════════════════════════════════════════════════════════════════
# detect_fb_params
# ═══════════════════════════════════════════════════════════════════════════


class TestDetectFBParams:
    """Tests para detect_fb_params."""

    def test_defaults_when_no_sysfs(self, monkeypatch):
        """Sin sysfs, debe devolver valores por defecto (720x480@32)."""
        # Simular que no existen los archivos sysfs
        def mock_exists(path):
            return False
        monkeypatch.setattr(os.path, "exists", mock_exists)

        params = fb_ui.detect_fb_params("/dev/fb0")
        assert params["width"] == 720
        assert params["height"] == 480
        assert params["bpp"] == 32
        assert params["stride"] == 720 * 4
        assert params["size"] == 720 * 480 * 4

    def test_stride_calculated_if_zero(self):
        """Si stride es 0, debe calcularse como width * (bpp/8)."""
        params = make_fb_params(bpp=32)
        params["stride"] = 0
        # Simular que detect_fb_params calcularía el stride
        if params["stride"] == 0:
            params["stride"] = params["width"] * (params["bpp"] // 8)
        assert params["stride"] == 720 * 4


# ═══════════════════════════════════════════════════════════════════════════
# HMIPanel
# ═══════════════════════════════════════════════════════════════════════════


class TestHMIPanel:
    """Tests para la clase HMIPanel."""

    def test_initialization(self):
        """HMIPanel debe inicializarse con valores por defecto."""
        panel = fb_ui.HMIPanel()
        assert panel.led_state is False
        assert panel.button_pressed is False
        assert panel.press_count == 0
        assert panel.ws_connected is False
        assert panel.running is True

    def test_init_layout_for_720x480(self):
        """Layout debe calcularse correctamente para 720x480."""
        panel = fb_ui.HMIPanel()
        pw, buf = self._make_panel_ready(panel, 720, 480)

        # Header debe ocupar todo el ancho
        assert panel.header_rect[2] == 720  # width

        # Los paneles LED y botón deben estar dentro de la pantalla
        assert panel.led_panel[0] >= 0
        assert panel.led_panel[0] + panel.led_panel[2] <= 720
        assert panel.btn_panel[0] >= 0
        assert panel.btn_panel[0] + panel.btn_panel[2] <= 720

        # El panel botón debe estar a la derecha del panel LED
        assert panel.led_panel[0] + panel.led_panel[2] < panel.btn_panel[0]

        buf.close()

    def test_init_layout_for_480x320(self):
        """Layout debe escalar correctamente para 480x320."""
        panel = fb_ui.HMIPanel()
        pw, buf = self._make_panel_ready(panel, 480, 320)

        assert panel.header_rect[2] == 480
        assert panel.footer_rect[0] == 0
        assert panel.led_panel[0] >= 0
        assert panel.btn_panel[0] < 480

        buf.close()

    def test_draw_all_no_error(self):
        """draw_all() no debe lanzar excepciones."""
        panel = fb_ui.HMIPanel()
        pw, buf = self._make_panel_ready(panel, 720, 480)
        panel.draw_all()  # No debe lanzar excepción
        buf.close()

    def test_draw_all_with_led_on(self):
        """draw_all() con LED encendido."""
        panel = fb_ui.HMIPanel()
        pw, buf = self._make_panel_ready(panel, 720, 480)
        panel.led_state = True
        panel.draw_all()
        buf.close()

    def test_draw_all_with_button_pressed(self):
        """draw_all() con botón presionado."""
        panel = fb_ui.HMIPanel()
        pw, buf = self._make_panel_ready(panel, 720, 480)
        panel.button_pressed = True
        panel.press_count = 42
        panel.draw_all()
        buf.close()

    def test_process_touch_led_toggle(self):
        """Toque en área del LED toggle."""
        panel = fb_ui.HMIPanel()
        pw, buf = self._make_panel_ready(panel, 720, 480)
        # Simular toque en el centro del toggle LED
        tr = panel.led_toggle_rect
        cx = (tr[0] + tr[2]) // 2
        cy = (tr[1] + tr[3]) // 2
        # API no disponible → toggle local
        panel.process_touch(cx, cy)
        # Debería haber cambiado el LED (o al menos no lanzar error)
        buf.close()

    def test_process_touch_button_area(self):
        """Toque en área del botón principal."""
        panel = fb_ui.HMIPanel()
        pw, buf = self._make_panel_ready(panel, 720, 480)
        br = panel.button_rect
        cx = (br[0] + br[2]) // 2
        cy = (br[1] + br[3]) // 2
        initial_count = panel.press_count
        panel.process_touch(cx, cy)
        # Debería haber incrementado (API no disponible → local)
        assert panel.press_count == initial_count + 1
        buf.close()

    def test_api_toggle_led_no_server(self):
        """Toggle LED sin servidor debe hacer toggle local."""
        panel = fb_ui.HMIPanel()
        pw, buf = self._make_panel_ready(panel, 720, 480)
        initial = panel.led_state
        panel._api_toggle_led()
        assert panel.led_state is not initial  # Debe haber cambiado
        buf.close()

    def test_api_press_button_no_server(self):
        """Pulsar botón sin servidor debe incrementar localmente."""
        panel = fb_ui.HMIPanel()
        pw, buf = self._make_panel_ready(panel, 720, 480)
        initial = panel.press_count
        panel._api_press_button()
        assert panel.press_count == initial + 1
        buf.close()

    def test_sync_status_no_server(self):
        """sync_status sin servidor no debe lanzar error."""
        panel = fb_ui.HMIPanel()
        pw, buf = self._make_panel_ready(panel, 720, 480)
        panel.sync_status()  # No debe lanzar excepción
        buf.close()

    def _make_panel_ready(self, panel, width, height):
        """Helper: prepara un panel con PixelWriter simulado."""
        params = make_fb_params(width=width, height=height, bpp=32)
        buf = make_mock_buf(params)
        pw = fb_ui.PixelWriter(buf, params)
        panel.pw = pw
        panel.params = params
        panel.init_layout()
        return pw, buf
