/**
 * useWebSocket — Conexion WebSocket al backend con reconexion automatica.
 * Sincroniza el estado global reactivamente.
 *
 * Incluye:
 *  - Validacion runtime de mensajes entrantes via Zod (safeParse, sin casts)
 *  - Sequence tracking con maquina de estados NORMAL -> RESYNCING -> NORMAL:
 *    al detectar un gap se descartan los eventos WS hasta que el snapshot
 *    REST de /api/status complete, evitando mezclar eventos WS con el snapshot.
 */

import { createSignal, onCleanup } from "solid-js";
import { ServerMessageSchema, SystemStatusSchema } from "@/schemas/ws";
import type { ClientMessage, ServerMessage } from "@/types/api";

const WS_URL = `${location.protocol === "https:" ? "wss:" : "ws:"}//${location.host}/ws`;
const RECONNECT_DELAY = 2000;

type SyncState = "normal" | "resyncing";

export function useWebSocket(onMessage: (msg: ServerMessage) => void) {
  const [connected, setConnected] = createSignal(false);
  let ws: WebSocket | null = null;
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  let shouldReconnect = true;
  let lastSequence: number | null = null;
  let syncState: SyncState = "normal";

  /** Recupera el estado completo via /api/status y re-baseline la secuencia. */
  async function resync() {
    try {
      const resp = await fetch("/api/status");
      if (!resp.ok) {
        throw new Error(`/api/status respondio ${resp.status}`);
      }

      const parsed = SystemStatusSchema.safeParse(await resp.json());
      if (!parsed.success) {
        console.warn("useWebSocket: snapshot /api/status invalido", parsed.error.flatten());
        return;
      }

      // Snapshot completo: se emite como status_update y se re-baseline la secuencia.
      onMessage({
        type: "status_update",
        data: parsed.data,
        timestamp: new Date().toISOString(),
        version: "1.0",
        sequence: null,
      });
      lastSequence = null;
      console.info("useWebSocket: resync completado via /api/status");
    } catch (err) {
      console.warn("useWebSocket: resync fallido", err);
    } finally {
      syncState = "normal";
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
      // Nueva conexion: re-baseline de secuencia y estado de sincronizacion.
      lastSequence = null;
      syncState = "normal";
      // Suscribirse a todos los topicos
      send({ type: "subscribe", topics: ["led", "button", "display", "system"], version: "1.0" });
      // Pedir estado inicial
      send({ type: "get_status", version: "1.0" });
    };

    ws.onmessage = (event) => {
      try {
        const parsed = ServerMessageSchema.safeParse(JSON.parse(event.data));
        if (!parsed.success) {
          console.warn("useWebSocket: mensaje invalido, ignorado", parsed.error.flatten());
          return;
        }
        const msg: ServerMessage = parsed.data;

        // Durante RESYNCING se descartan los eventos WS para no mezclarlos
        // con el snapshot REST en curso.
        if (syncState === "resyncing") {
          return;
        }

        // Sequence tracking: detectar gaps.
        if (typeof msg.sequence === "number") {
          if (lastSequence !== null && msg.sequence > lastSequence + 1) {
            console.warn(
              `useWebSocket: gap detectado (last=${lastSequence}, current=${msg.sequence}), resync...`,
            );
            syncState = "resyncing";
            void resync();
            return;
          }
          lastSequence = msg.sequence;
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
