"""Tests para modelos Pydantic: DeviceConfig, ClientMessage, ServerMessage, SystemStatus."""

from __future__ import annotations

import tempfile
from datetime import UTC
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from backend.app.models.device import DeviceConfig, DeviceType, PinMapping, load_devices
from backend.app.models.events import ClientMessage, ServerMessage, SubscriptionTopic
from backend.app.models.hmi import ButtonState, DisplayInfo, LedState, SystemStatus

# ── DeviceConfig ────────────────────────────────────────────────


class TestDeviceConfig:
    """Validacion de DeviceConfig y PinMapping."""

    def test_valid_device_config_minimal(self):
        """DeviceConfig minimo se construye sin errores."""
        cfg = DeviceConfig(id="led1", type=DeviceType.DIGITAL_OUTPUT, name="LED")
        assert cfg.id == "led1"
        assert cfg.type == DeviceType.DIGITAL_OUTPUT
        assert cfg.name == "LED"
        assert cfg.pin is None
        assert cfg.kwargs == {}

    def test_pin_bcm_too_low_raises(self):
        """pin.bcm=0 lanza ValidationError (ge=2)."""
        with pytest.raises(ValidationError):
            PinMapping(bcm=0, name="TEST")

    def test_pin_bcm_too_high_raises(self):
        """pin.bcm=28 lanza ValidationError (le=27)."""
        with pytest.raises(ValidationError):
            PinMapping(bcm=28, name="TEST")

    def test_pin_name_too_long_raises(self):
        """pin.name mayor que max_length=32 lanza ValidationError."""
        with pytest.raises(ValidationError):
            PinMapping(bcm=17, name="A" * 33)

    def test_load_devices_from_valid_yaml(self):
        """Crea YAML temporal con un dispositivo, llama load_devices, verifica resultado."""
        yaml_content = {
            "devices": [
                {
                    "id": "led1",
                    "type": "digital_output",
                    "name": "LED 1",
                    "pin": {"bcm": 17, "name": "LED_ROJO"},
                }
            ]
        }
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False, encoding="utf-8"
        ) as tmp:
            yaml.safe_dump(yaml_content, tmp)
            tmp_path = tmp.name

        try:
            devices = load_devices(tmp_path)
            assert isinstance(devices, dict)
            assert "led1" in devices
            assert devices["led1"].type == DeviceType.DIGITAL_OUTPUT
            assert devices["led1"].pin is not None
            assert devices["led1"].pin.bcm == 17
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def test_load_devices_empty_yaml(self):
        """YAML vacio -> load_devices retorna dict vacio."""
        yaml_content = {}
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False, encoding="utf-8"
        ) as tmp:
            yaml.safe_dump(yaml_content, tmp)
            tmp_path = tmp.name

        try:
            devices = load_devices(tmp_path)
            assert devices == {}
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def test_load_devices_missing_file(self):
        """Fichero inexistente -> lanza FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            load_devices("/nonexistent/path/devices.yaml")

    def test_device_type_enum_values(self):
        """Verifica que DeviceType tenga los valores esperados."""
        assert DeviceType.DIGITAL_OUTPUT == "digital_output"
        assert DeviceType.DIGITAL_INPUT == "digital_input"
        assert DeviceType.ANALOG_INPUT == "analog_input"
        assert DeviceType.PWM_OUTPUT == "pwm_output"
        assert DeviceType.I2C_DEVICE == "i2c_device"
        assert DeviceType.SPI_DEVICE == "spi_device"
        # StrEnum: el valor es la propia cadena
        assert isinstance(DeviceType.DIGITAL_OUTPUT, str)


# ── ClientMessage ──────────────────────────────────────────────


class TestClientMessage:
    """Validacion de mensajes cliente -> servidor."""

    def test_valid_toggle_led_message(self):
        """ClientMessage(type='toggle_led') es valido."""
        msg = ClientMessage(type="toggle_led", version="1.0")
        assert msg.type == "toggle_led"
        assert msg.version == "1.0"
        assert msg.topics is None

    def test_valid_subscribe_with_topics(self):
        """ClientMessage(type='subscribe', topics=[...]) es valido."""
        msg = ClientMessage(
            type="subscribe",
            topics=[SubscriptionTopic.LED, SubscriptionTopic.BUTTON],
            version="1.0",
        )
        assert msg.type == "subscribe"
        assert len(msg.topics) == 2
        assert SubscriptionTopic.LED in msg.topics

    def test_invalid_type_raises(self):
        """Tipo invalido lanza ValidationError."""
        with pytest.raises(ValidationError):
            ClientMessage(type="invalid_type")

    def test_missing_version_defaults(self):
        """Si version no se pasa, usa el default '1.0'."""
        msg = ClientMessage(type="get_status")
        assert msg.version == "1.0"


# ── ServerMessage ──────────────────────────────────────────────


class TestServerMessage:
    """Validacion de mensajes servidor -> cliente."""

    def test_server_message_sequence_default(self):
        """sequence por defecto es None."""
        msg = ServerMessage(type="led_changed", data={"state": True})
        assert msg.sequence is None

    def test_server_message_with_timestamp(self):
        """timestamp se genera automaticamente si no se pasa."""
        from datetime import datetime

        msg = ServerMessage(type="led_changed", data={"state": True})
        assert msg.timestamp is not None
        assert isinstance(msg.timestamp, datetime)
        # Debe ser un timestamp reciente (UTC)
        delta = datetime.now(UTC) - msg.timestamp
        assert abs(delta.total_seconds()) < 5


# ── SystemStatus ───────────────────────────────────────────────


class TestSystemStatus:
    """Validacion de SystemStatus.from_manager."""

    def test_from_manager_creates_correct_status(self):
        """from_manager crea SystemStatus con todos los campos correctos."""
        led = LedState(state=True, label="ENCENDIDO", gpio_pin=17)
        btn = ButtonState(pressed=False, press_count=3)
        display = DisplayInfo(connected=True, resolution="480x320", driver="ili9486")

        status = SystemStatus.from_manager(
            led=led, button=btn, display=display, ws_count=5, uptime_seconds=42.5
        )

        assert status.led.state is True
        assert status.button.press_count == 3
        assert status.display is not None
        assert status.display.connected is True
        assert status.uptime_seconds == 42.5
        assert status.websocket_clients == 5
        # cpu_temp_celsius puede ser None en entornos sin /sys
        assert status.cpu_temp_celsius is None or isinstance(status.cpu_temp_celsius, float)
        from datetime import datetime

        assert isinstance(status.timestamp, datetime)

    def test_from_manager_without_display(self):
        """Sin display, el campo display es None."""
        led = LedState(state=False, label="APAGADO", gpio_pin=17)
        btn = ButtonState(pressed=False, press_count=0)

        status = SystemStatus.from_manager(
            led=led, button=btn, display=None, ws_count=0, uptime_seconds=10.0
        )

        assert status.display is None
        assert status.led.state is False
