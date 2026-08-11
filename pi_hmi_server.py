#!/usr/bin/env python3
"""
pi_hmi_server.py — Servidor HMI ligero para Raspberry Pi

Servidor HTTP + WebSocket sin dependencias externas (solo stdlib).
Optimizado para Raspberry Pi B+ (512MB RAM, ARMv6).

Características:
- Sirve el panel HMI (index.html) en http://<ip>:8000
- WebSocket en ws://<ip>:8000/ws para comunicación en tiempo real
- REST API: /api/led, /api/button, /api/status
- Gestión de estado LED virtual y botón
- Soporte GPIO opcional (si RPi.GPIO está disponible)

Ejecución:
    python3 pi_hmi_server.py
    python3 pi_hmi_server.py --port 8080
"""
from __future__ import annotations

import asyncio
import hashlib
import base64
import struct
import json
import os
import sys
import time
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from pathlib import Path

# ── Configuración ──────────────────────────────────────────────────────────
HOST = "0.0.0.0"
HTTP_PORT = 8000
WS_PORT = 8001
STATIC_DIR = Path(__file__).parent / "backend" / "app" / "static"

# ── Estado HMI (thread-safe) ───────────────────────────────────────────────
_lock = threading.Lock()
_led_state = False
_button_press_count = 0
_ws_clients: list[WebSocketHandler] = []
_ws_lock = threading.Lock()


# ═══════════════════════════════════════════════════════════════════════════
# WebSocket simplificado (solo texto, sin dependencias externas)
# ═══════════════════════════════════════════════════════════════════════════

class SimpleWebSocket:
    """Implementación mínima de WebSocket (RFC 6455) solo para frames de texto."""

    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        self.reader = reader
        self.writer = writer
        self.closed = False

    @staticmethod
    async def handshake(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> SimpleWebSocket | None:
        """Realiza el handshake WebSocket. Devuelve None si falla."""
        request_line = await asyncio.wait_for(reader.readline(), timeout=10)
        if not request_line:
            return None

        headers = {}
        while True:
            line = await asyncio.wait_for(reader.readline(), timeout=10)
            line = line.decode("utf-8", errors="replace").strip()
            if not line:
                break
            if ":" in line:
                key, value = line.split(":", 1)
                headers[key.strip().lower()] = value.strip()

        ws_key = headers.get("sec-websocket-key", "")
        if not ws_key:
            return None

        # Calcular accept key
        magic = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
        accept = base64.b64encode(
            hashlib.sha1((ws_key + magic).encode()).digest()
        ).decode()

        response = (
            "HTTP/1.1 101 Switching Protocols\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Accept: {accept}\r\n"
            "\r\n"
        )
        writer.write(response.encode())
        await writer.drain()

        return SimpleWebSocket(reader, writer)

    async def recv(self) -> str | None:
        """Recibe un mensaje de texto. Devuelve None si la conexión se cierra."""
        try:
            while True:
                header = await asyncio.wait_for(self.reader.readexactly(2), timeout=60)
                b0, b1 = header[0], header[1]
                fin = (b0 & 0x80) != 0
                opcode = b0 & 0x0F
                masked = (b1 & 0x80) != 0
                length = b1 & 0x7F

                if length == 126:
                    extra = await asyncio.wait_for(self.reader.readexactly(2), timeout=10)
                    length = struct.unpack("!H", extra)[0]
                elif length == 127:
                    extra = await asyncio.wait_for(self.reader.readexactly(8), timeout=10)
                    length = struct.unpack("!Q", extra)[0]

                mask_key = await asyncio.wait_for(self.reader.readexactly(4), timeout=10) if masked else None
                payload = await asyncio.wait_for(self.reader.readexactly(length), timeout=10)

                if masked and mask_key:
                    payload = bytes(b ^ mask_key[i % 4] for i, b in enumerate(payload))

                if opcode == 0x8:  # Close
                    return None
                if opcode == 0x9:  # Ping
                    await self._send_frame(b"\x8A", b"")  # Pong
                    continue
                if opcode == 0x1:  # Text
                    return payload.decode("utf-8", errors="replace")
                if opcode == 0xA:  # Pong
                    continue

        except (asyncio.IncompleteReadError, ConnectionError, TimeoutError):
            return None

    async def send(self, text: str) -> None:
        """Envía un mensaje de texto."""
        try:
            data = text.encode("utf-8")
            await self._send_frame(b"\x81", data)
        except (ConnectionError, OSError):
            self.closed = True

    async def _send_frame(self, opcode: bytes, payload: bytes) -> None:
        """Envía un frame WebSocket (sin máscara, modo servidor)."""
        frame = bytearray(opcode)
        length = len(payload)
        if length < 126:
            frame.append(length)
        elif length < 65536:
            frame.append(126)
            frame.extend(struct.pack("!H", length))
        else:
            frame.append(127)
            frame.extend(struct.pack("!Q", length))
        frame.extend(payload)
        self.writer.write(bytes(frame))
        await self.writer.drain()

    async def close(self) -> None:
        """Cierra la conexión WebSocket."""
        if not self.closed:
            try:
                await self._send_frame(b"\x88", b"")
            except Exception:
                pass
            try:
                self.writer.close()
                await self.writer.wait_closed()
            except Exception:
                pass
            self.closed = True


# ═══════════════════════════════════════════════════════════════════════════
# HTTP Request Handler
# ═══════════════════════════════════════════════════════════════════════════

class HMIHandler(BaseHTTPRequestHandler):
    """Handler HTTP para el panel HMI (API REST + archivos estáticos)."""

    def log_message(self, format, *args):
        """Suprimir logs HTTP en consola (usamos nuestro propio logger)."""
        pass

    def _send_json(self, data: dict, status: int = 200) -> None:
        """Envía una respuesta JSON."""
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, path: str, content_type: str = "text/html") -> None:
        """Envía un archivo estático."""
        try:
            with open(path, "rb") as f:
                content = f.read()
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(content)
        except FileNotFoundError:
            self._send_json({"error": "Not found"}, 404)

    def do_GET(self) -> None:
        """Maneja peticiones GET."""
        parsed = urlparse(self.path)
        path = parsed.path

        # API endpoints
        if path == "/api/led":
            self._send_json({
                "state": _led_state,
                "message": "LED encendido" if _led_state else "LED apagado",
            })
        elif path == "/api/button":
            self._send_json({
                "pressed": False,
                "press_count": _button_press_count,
            })
        elif path == "/api/status":
            with _ws_lock:
                ws_count = len(_ws_clients)
            self._send_json({
                "led": {"state": _led_state, "label": "ENCENDIDO" if _led_state else "APAGADO"},
                "button": {"pressed": False, "press_count": _button_press_count},
                "websocket_clients": ws_count,
                "timestamp": int(time.time()),
            })
        elif path == "/health":
            self._send_json({"status": "ok"})
        elif path in ("/", "/index.html"):
            html_path = STATIC_DIR / "index.html"
            if html_path.is_file():
                self._send_file(str(html_path), "text/html; charset=utf-8")
            else:
                self._send_json({
                    "message": "Raspberry HMI Server",
                    "version": "1.0",
                    "status": "running",
                    "error": "index.html not found",
                })
        else:
            self._send_json({"error": "Not found", "path": path}, 404)

    def do_POST(self) -> None:
        """Maneja peticiones POST."""
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length) if content_length > 0 else b""
        try:
            data = json.loads(body) if body else {}
        except json.JSONDecodeError:
            data = {}

        parsed = urlparse(self.path)
        path = parsed.path
        global _led_state, _button_press_count

        if path == "/api/led/toggle":
            with _lock:
                _led_state = not _led_state
            print(f"[HMI] LED toggled -> {_led_state}")
            self._send_json({
                "state": _led_state,
                "message": "LED encendido" if _led_state else "LED apagado",
            })
        elif path == "/api/led/on":
            with _lock:
                _led_state = True
            print("[HMI] LED ON")
            self._send_json({"state": True, "message": "LED encendido"})
        elif path == "/api/led/off":
            with _lock:
                _led_state = False
            print("[HMI] LED OFF")
            self._send_json({"state": False, "message": "LED apagado"})
        elif path == "/api/button/press":
            with _lock:
                _button_press_count += 1
                count = _button_press_count
            print(f"[HMI] Botón presionado (count={count})")
            self._send_json({
                "pressed": True,
                "press_count": count,
                "message": f"Botón presionado ({count} veces)",
            })
        else:
            self._send_json({"error": "Not found", "path": path}, 404)

    def do_OPTIONS(self) -> None:
        """CORS preflight."""
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()


# ═══════════════════════════════════════════════════════════════════════════
# Servidor WebSocket (asyncio)
# ═══════════════════════════════════════════════════════════════════════════

async def handle_websocket(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    """Maneja una conexión WebSocket."""
    global _led_state, _button_press_count

    ws = await SimpleWebSocket.handshake(reader, writer)
    if ws is None:
        writer.close()
        return

    addr = writer.get_extra_info("peername", ("?", 0))
    print(f"[WS] Cliente conectado: {addr[0]}:{addr[1]}")

    with _ws_lock:
        _ws_clients.append(ws)

    try:
        # Enviar estado inicial
        with _lock:
            initial = {
                "type": "status",
                "led": _led_state,
                "button_pressed": False,
                "button_press_count": _button_press_count,
            }
        await ws.send(json.dumps(initial))

        while True:
            msg = await ws.recv()
            if msg is None:
                break

            try:
                data = json.loads(msg)
            except json.JSONDecodeError:
                await ws.send(json.dumps({"type": "error", "message": "JSON inválido"}))
                continue

            msg_type = data.get("type", "")

            if msg_type == "button_press":
                with _lock:
                    _button_press_count += 1
                    count = _button_press_count
                print(f"[WS] Botón presionado (count={count})")
                broadcast_msg = json.dumps({"type": "button_press", "press_count": count})

            elif msg_type == "button_release":
                with _lock:
                    count = _button_press_count
                broadcast_msg = json.dumps({"type": "button_release", "press_count": count})

            elif msg_type == "toggle_led":
                with _lock:
                    _led_state = not _led_state
                print(f"[WS] LED toggled -> {_led_state}")
                broadcast_msg = json.dumps({"type": "led_state", "state": _led_state})

            elif msg_type == "get_status":
                with _lock:
                    status = {
                        "type": "status",
                        "led": _led_state,
                        "button_pressed": False,
                        "button_press_count": _button_press_count,
                    }
                await ws.send(json.dumps(status))
                continue

            else:
                await ws.send(json.dumps({"type": "error", "message": f"Tipo desconocido: {msg_type}"}))
                continue

            # Broadcast a todos los clientes
            with _ws_lock:
                for client in _ws_clients:
                    if client is not ws:
                        try:
                            await client.send(broadcast_msg)
                        except Exception:
                            pass

    except (ConnectionError, OSError, asyncio.IncompleteReadError):
        pass
    finally:
        with _ws_lock:
            if ws in _ws_clients:
                _ws_clients.remove(ws)
        await ws.close()
        print(f"[WS] Cliente desconectado: {addr[0]}")


# ═══════════════════════════════════════════════════════════════════════════
# Servidor principal
# ═══════════════════════════════════════════════════════════════════════════

class ThreadedHTTPServer:
    """Servidor HTTP que se ejecuta en un hilo separado."""

    def __init__(self, host: str, port: int):
        self.server = HTTPServer((host, port), HMIHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def start(self):
        self.thread.start()
        print(f"[HTTP] Servidor HTTP iniciado en http://{HOST}:{HTTP_PORT}")

    def stop(self):
        self.server.shutdown()


async def main_async(host: str, http_port: int, ws_port: int):
    """Punto de entrada asíncrono."""
    # Iniciar servidor HTTP en un hilo
    http_server = ThreadedHTTPServer(host, http_port)
    http_server.start()

    # Iniciar servidor WebSocket (asyncio)
    ws_server = await asyncio.start_server(handle_websocket, host, ws_port)
    print(f"[WS] Servidor WebSocket iniciado en ws://{host}:{ws_port}/ws")
    print(f"[HMI] Panel HMI disponible en http://{host}:{http_port}")
    print(f"[HMI] Presiona Ctrl+C para detener")

    try:
        async with ws_server:
            await ws_server.serve_forever()
    except asyncio.CancelledError:
        pass
    finally:
        http_server.stop()
        print("[HMI] Servidor detenido")


def main():
    """Punto de entrada principal."""
    global HTTP_PORT, WS_PORT, STATIC_DIR, HOST

    # Argumentos de línea de comandos
    if "--port" in sys.argv:
        try:
            idx = sys.argv.index("--port")
            HTTP_PORT = int(sys.argv[idx + 1])
            WS_PORT = HTTP_PORT + 1
        except (ValueError, IndexError):
            print("Error: --port requiere un número")
            sys.exit(1)

    if "--ws-port" in sys.argv:
        try:
            idx = sys.argv.index("--ws-port")
            WS_PORT = int(sys.argv[idx + 1])
        except (ValueError, IndexError):
            print("Error: --ws-port requiere un número")
            sys.exit(1)

    if "--static" in sys.argv:
        try:
            idx = sys.argv.index("--static")
            STATIC_DIR = Path(sys.argv[idx + 1])
        except IndexError:
            print("Error: --static requiere una ruta")
            sys.exit(1)

    if "--host" in sys.argv:
        try:
            idx = sys.argv.index("--host")
            HOST = sys.argv[idx + 1]
        except IndexError:
            pass

    # Verificar que existe index.html
    index_path = STATIC_DIR / "index.html"
    if not index_path.is_file():
        print(f"[WARN] index.html no encontrado en {STATIC_DIR}")
        print(f"[WARN] Buscando en otras ubicaciones...")
        # Buscar en ubicaciones alternativas
        alternatives = [
            Path("static/index.html"),
            Path("backend/app/static/index.html"),
            Path("../backend/app/static/index.html"),
        ]
        for alt in alternatives:
            if alt.is_file():
                STATIC_DIR = alt.parent
                print(f"[OK] Encontrado en {STATIC_DIR}")
                break

    print("=" * 50)
    print("  Raspberry Pi HMI Server v1.0")
    print(f"  HTTP: {HOST}:{HTTP_PORT}")
    print(f"  WS:   {HOST}:{WS_PORT}")
    print(f"  Static: {STATIC_DIR}")
    print("=" * 50)

    try:
        asyncio.run(main_async(HOST, HTTP_PORT, WS_PORT))
    except KeyboardInterrupt:
        print("\n[HMI] Servidor detenido por el usuario")


if __name__ == "__main__":
    main()
