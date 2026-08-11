"""
blink_test.py
=============

Prueba de parpadeo basada en el registro de dispositivos declarativo
(`backend/config/devices.yaml`).

Ejemplo de uso:
  python3 diagnostics/gpio/blink_test.py led1 --times 3

El test usa MockGPIODriver por defecto para evitar tocar hardware
accidentalmente durante la fase de diseño. Cuando se implemente
RealGPIODriver, el script se podrá ejecutar en la Raspberry con
permisos adecuados.
"""
from __future__ import annotations

import argparse
import logging
import time
from pathlib import Path
from typing import Dict

from backend.app.hardware.hal import load_devices, MockGPIODriver, GPIODriver

logger = logging.getLogger("diagnostics.gpio.blink")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Blink test using device registry")
    p.add_argument("device_id", type=str, help="Device id defined in devices.yaml (eg: led1)")
    p.add_argument("--devices", type=Path, default=Path("backend/config/devices.yaml"), help="Path to devices.yaml")
    p.add_argument("--times", type=int, default=3, help="Veces a parpadear")
    p.add_argument("--on-time", type=float, default=0.5)
    p.add_argument("--off-time", type=float, default=0.5)
    return p.parse_args()


def blink_test(device_id: str, devices_path: Path, times: int, on_time: float, off_time: float, driver: GPIODriver | None = None) -> None:
    devices: Dict[str, object] = load_devices(str(devices_path))
    if device_id not in devices:
        raise SystemExit(f"Device {device_id} not found in {devices_path}")

    dev = devices[device_id]
    if dev.config.get("driver") != "gpio":
        raise SystemExit("blink_test only supports devices with driver=gpio for now")

    pin = int(dev.config.get("pin"))

    if driver is None:
        driver = MockGPIODriver()

    logger.info("Setting up pin %s as output", pin)
    driver.setup_output(pin)

    for i in range(times):
        logger.info("Blink %d/%d: ON", i + 1, times)
        driver.set_high(pin)
        time.sleep(on_time)
        logger.info("Blink %d/%d: OFF", i + 1, times)
        driver.set_low(pin)
        time.sleep(off_time)

    driver.cleanup()
    logger.info("Blink test finished for %s", device_id)


def main() -> None:
    args = parse_args()
    blink_test(args.device_id, args.devices, args.times, args.on_time, args.off_time)


if __name__ == "__main__":
    main()
