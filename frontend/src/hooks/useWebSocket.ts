/**
 * useWebSocket — Conexion WebSocket al backend con reconexion automatica.
 * Sincroniza el estado global reactivamente.
 *
 * Incluye:
 *  - Sequence tracking para detectar gaps y disparar resync
 *  - Validacion runtime de mensajes entrantes
 */

import { createSignal, onCleanup } from "solid-js";
import type { ClientMessage, ServerMessage, SystemStatus } from "@/types/api";

const WS_URL = `${location.protocol === "https:" ? "wss:" : "ws:"}//${location.host}/ws`;
const RECONNECT_DELAY = 2000;

/** Tipos de mensaje conocidos y campos esperados en data */
const KNOWN_TYPES: Record<string, string[]> = {
  led_changed: ["state"],
  button_pressed: ["press_count"],
  button_released: ["press_count"],
  status_update: ["led", "button", "timestamp"],
  display_changed: ["connected", "resolution", "driver"],
  error: ["code", "message"],
};

function validateMessage(raw: Record<string, unknown>): ServerMessage | null {
  // Validacion basica: type string
  if (typeof raw.type !== "string") {
    console.warn("useWebSocket: mensaje sin type valido, ignorado", raw);
    return null;
  }

  // data debe ser un objeto (no null, no array)
  if (raw.data === null || typeof raw.data !== "object" || Array.isArray(raw.data)) {
    console.warn("useWebSocket: data no es un objeto valido, ignorado", raw);
    return null;
  }

  const data = raw.data as Record<string, unknown>;

  // Si el tipo es conocido, validar campos esperados
  const expectedFields = KNOWN_TYPES[raw.type];
  if (expectedFields) {
    for (const field of expectedFields) {
      if (!(field in data)) {
        console.warn(
          `useWebSocket: mensaje tipo "${raw.type}" sin campo "${field}", ignorado`,
          raw,
        );
        return null;
      }
    }
  }

  return raw as unknown as ServerMessage;
}

export function useWebSocket(onMessage: (msg: ServerMessage) => void) {
  const [connected, setConnected] = createSignal(false);
  let ws: WebSocket | null = null;
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  let shouldReconnect = true;
  let lastSequence = 0;

  /** Dispara un resync pidiendo /api/status */
  async function resync() {
    try {
      const resp = await fetch("/api/status");
      if (resp.ok) {
        const status: SystemStatus = await resp.json();
        onMessage({
          type: "status_update",
          data: status,
          timestamp: new Date().toISOString(),
          version: "1.0",
          sequence: 0,
        });
        console.info("useWebSocket: resync completado via /api/status");
      }
    } catch (err) {
      console.warn("useWebSocket: resync fallido", err);
    }
  }

  function connect() {
    if (ws?.readyState === WebSocket.OPEN || ws?.readyState === WebSocket.CONNECTING) {
      return;
    }

    try {
      ws = new WebSocket(WS_URL);
    } catch {
      scheduleReconnect();
      return;
    }

    ws.onopen = () => {
      setConnected(true);
      // Reset sequence on new connection
      lastSequence = 0;
      // Suscribirse a todos los topicos
      send({ type: "subscribe", topics: ["led", "button", "display", "system"], version: "1.0" });
      // Pedir estado inicial
      send({ type: "get_status", version: "1.0" });
    };

    ws.onmessage = (event) => {
      try {
        const raw = JSON.parse(event.data);

        // Validacion runtime mejorada
        const msg = validateMessage(raw);
        if (!msg) return;

        // Sequence tracking: detectar gaps
        if (typeof raw.sequence === "number" && raw.sequence > 0) {
          if (raw.sequence > lastSequence + 1) {
            console.warn(
              `useWebSocket: gap detectado (last=${lastSequence}, current=${raw.sequence}), resync...`,
            );
            lastSequence = raw.sequence;
            resync();
            return;
          }
          lastSequence = raw.sequence;
        }

        onMessage(msg);
      } catch {
        // Ignore malformed messages
      }
    };

    ws.onclose = () => {
      setConnected(false);
      ws = null;
      scheduleReconnect();
    };

    ws.onerror = () => {
      // onclose will fire after this
    };
  }

  function scheduleReconnect() {
    if (!shouldReconnect) return;
    if (reconnectTimer) clearTimeout(reconnectTimer);
    reconnectTimer = setTimeout(connect, RECONNECT_DELAY);
  }

  function send(msg: ClientMessage) {
    if (ws?.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify(msg));
    }
  }

  function disconnect() {
    shouldReconnect = false;
    if (reconnectTimer) {
      clearTimeout(reconnectTimer);
      reconnectTimer = null;
    }
    ws?.close();
    ws = null;
    setConnected(false);
  }

  // Auto-connect
  connect();

  onCleanup(disconnect);

  return {
    connected,
    send,
    disconnect,
  };
}
