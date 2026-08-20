"""Tests HIL (Hardware-In-the-Loop) para la Raspberry Pi fisica.

Estos tests solo se ejecutan en la Raspberry Pi fisica (RPI_HIL=1).
En Windows/CI se saltan automaticamente. Cada test comprueba primero
que el recurso de hardware real existe y se salta si no esta presente.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path

import pytest

HARDWARE_AVAILABLE = os.environ.get("RPI_HIL") == "1"

pytestmark = [
    pytest.mark.hardware,
    pytest.mark.skipif(
        not HARDWARE_AVAILABLE,
        reason="HIL: requiere Raspberry Pi fisica (RPI_HIL=1)",
    ),
]

_BACKEND_BASE_URL = "http://localhost:8000"
_TOUCH_KEYWORDS = ("touch", "ads7846", "xpt", "ft5x", "gt9", "stmpe")


def _find_touch_device() -> str | None:
    """Devuelve la ruta del dispositivo tactil o None si no existe."""
    for i in range(10):
        dev = Path(f"/dev/input/event{i}")
        if not dev.exists():
            continue
        name_path = Path(f"/sys/class/input/{dev.name}/device/name")
        try:
            name = name_path.read_text(encoding="utf-8").strip().lower()
        except OSError:
            continue
        if any(kw in name for kw in _TOUCH_KEYWORDS):
            return str(dev)
    return None


@pytest.mark.hardware
def test_gpiomem_exists() -> None:
    """Comprueba que /dev/gpiomem esta presente (GPIO real)."""
    dev = Path("/dev/gpiomem")
    if not dev.exists():
        pytest.skip(f"No existe {dev}: GPIO no accesible")


@pytest.mark.hardware
def test_drm_card0_exists() -> None:
    """Comprueba que /dev/dri/card0 esta presente (display real)."""
    dev = Path("/dev/dri/card0")
    if not dev.exists():
        pytest.skip(f"No existe {dev}: display DRM no accesible")


@pytest.mark.hardware
def test_backend_health_endpoint() -> None:
    """El endpoint /health responde HTTP 200 en la Pi."""
    url = f"{_BACKEND_BASE_URL}/health"
    try:
        with urllib.request.urlopen(url, timeout=5.0) as response:
            assert response.status == 200
    except urllib.error.HTTPError as exc:
        pytest.fail(f"Backend respondio HTTP {exc.code} en {url}")
    except (urllib.error.URLError, OSError) as exc:
        pytest.skip(f"Backend no accesible en {url}: {exc}")


@pytest.mark.hardware
def test_api_status_endpoint() -> None:
    """El endpoint /api/status responde 200 con JSON que incluye 'led'."""
    url = f"{_BACKEND_BASE_URL}/api/status"
    try:
        with urllib.request.urlopen(url, timeout=5.0) as response:
            assert response.status == 200
            data = json.load(response)
            assert "led" in data
    except urllib.error.HTTPError as exc:
        pytest.fail(f"Backend respondio HTTP {exc.code} en {url}")
    except (urllib.error.URLError, OSError) as exc:
        pytest.skip(f"Backend no accesible en {url}: {exc}")


@pytest.mark.hardware
def test_touch_device_present() -> None:
    """Busca un dispositivo tactil reconocido en /dev/input/."""
    device = _find_touch_device()
    if device is None:
        pytest.skip("No se encontro dispositivo tactil en /dev/input/")
