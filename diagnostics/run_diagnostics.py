"""
run_diagnostics.py
===================

Herramienta de diagnóstico reversible y no intrusiva para la Raspberry Pi.

Este script ejecuta una colección de comandos de lectura del sistema (sin
modificar la configuración) y genera un informe JSON y HTML en
diagnostics/report.json y diagnostics/report.html.

Se usa durante la Fase 0 para caracterizar el hardware (pantalla, touch,
GPIO, buses, red, USB, SSH). No cambia /boot/config.txt ni instala nada.

Uso:
  python3 run_diagnostics.py --output diagnostics/report

Requisitos: Python 3.8+, permisos para ejecutar comandos del sistema.
"""
from __future__ import annotations

import argparse
import json
import logging
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List

logger = logging.getLogger("diagnostics")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")


COMMANDS: Dict[str, List[str]] = {
    "system": [
        "cat /proc/device-tree/model",
        "uname -a",
        "cat /etc/os-release",
        "hostnamectl",
    ],
    "video": [
        "ls -l /dev/fb*",
        "dmesg | grep -iE 'spi|ads7846|xpt|fbtft|touch'",
        "lsmod | grep -iE 'fbtft|ads7846|spi|touch' || true",
        "grep -iE 'dtoverlay|dtparam' /boot/config.txt 2>/dev/null || true",
        "vcgencmd version 2>/dev/null || true",
        "fbset || true",
    ],
    "input": [
        "ls -l /dev/input/ || true",
        "cat /proc/bus/input/devices | grep -iE 'Name|Handlers' || true",
        "xinput list 2>/dev/null || true",
    ],
    "network": [
        "ip a",
        "ip route",
        "hostname -I || true",
        "ping -c 1 8.8.8.8 2>/dev/null || true",
        "ethtool eth0 2>/dev/null || true",
    ],
    "usb": [
        "lsusb 2>/dev/null || true",
        "dmesg | tail -n 100",
    ],
    "ssh": [
        "systemctl status ssh || true",
        "ss -tlnp 2>/dev/null || true",
    ],
}


def run_command(cmd: str) -> str:
    """Ejecuta un comando de shell y devuelve stdout+stderr como string.

    Los comandos usados son lecturas del sistema; se ejecutan con shell=True
    para poder usar tuberías/grep tal y como el administrador lo haría.
    """
    logger.debug("Ejecutando comando: %s", cmd)
    try:
        proc = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=20)
        out = proc.stdout.strip() + ("\n" + proc.stderr.strip() if proc.stderr else "")
        return out.strip()
    except Exception as e:
        logger.exception("Fallo ejecutando comando: %s", cmd)
        return f"ERROR: {e}"


def gather_report() -> Dict[str, Any]:
    """Recopila la salida de todos los comandos en una estructura dict."""
    report: Dict[str, Any] = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "commands": {},
    }

    for section, cmds in COMMANDS.items():
        report["commands"][section] = {}
        for cmd in cmds:
            report["commands"][section][cmd] = run_command(cmd)

    return report


def write_outputs(base: Path, report: Dict[str, Any]) -> None:
    """Escribe report.json y un HTML simple para visualización rápida."""
    base.mkdir(parents=True, exist_ok=True)
    json_path = base.with_suffix(".json")
    html_path = base.with_suffix(".html")

    with json_path.open("w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, ensure_ascii=False)

    # HTML very small viewer
    html_parts: List[str] = [
        "<html><head><meta charset=\"utf-8\"><title>Diagnostics report</title></head><body>",
        f"<h1>Diagnostics report - {report.get('generated_at')}</h1>",
    ]
    for section, cmds in report.get("commands", {}).items():
        html_parts.append(f"<h2>{section}</h2>")
        for cmd, out in cmds.items():
            html_parts.append(f"<h3>{cmd}</h3><pre>{out}</pre>")

    html_parts.append("</body></html>")
    with html_path.open("w", encoding="utf-8") as fh:
        fh.write("\n".join(html_parts))

    logger.info("Wrote report: %s and %s", json_path, html_path)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run system diagnostics and produce report files.")
    p.add_argument("--output", type=Path, default=Path("diagnostics/report"), help="Base output path (no extension)")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    out_base: Path = args.output
    logger.info("Starting diagnostics, output base=%s", out_base)
    report = gather_report()
    write_outputs(out_base, report)


if __name__ == "__main__":
    main()
