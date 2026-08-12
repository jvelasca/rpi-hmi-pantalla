/**
 * useWebSocket — Conexion WebSocket al backend con reconexion automatica.
 * Sincroniza el estado global reactivamente.
 */

import { createSignal, onCleanup } from "solid-js";
import type { ClientMessage, ServerMessage, SystemStatus } from "@/types/api";

const WS_URL = `${location.protocol === "https:" ? "wss:" : "ws:"}//${location.host}/ws`;
const RECONNECT_DELAY = 2000;

export function useWebSocket(onMessage: (msg: ServerMessage) => void) {
  const [connected, setConnected] = createSignal(false);
  let ws: WebSocket | null = null;
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  let shouldReconnect = true;

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
      // Suscribirse a todos los topicos
      send({ type: "subscribe", topics: ["led", "button", "display", "system"], version: "1.0" });
      // Pedir estado inicial
      send({ type: "get_status", version: "1.0" });
    };

    ws.onmessage = (event) => {
      try {
        const raw = JSON.parse(event.data);
        if (typeof raw.type !== "string") {
          console.warn("useWebSocket: mensaje sin tipo valido, ignorado", raw);
          return;
        }
        const msg = raw as ServerMessage;
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
