/**
 * useWebSocket — Conexion WebSocket al backend con reconexion automatica.
 * Sincroniza el estado global reactivamente.
 *
 * Incluye:
 *  - Validacion runtime de mensajes entrantes via Zod (safeParse, sin casts)
 *  - Sequence tracking POR-TOPIC con maquina de estados NORMAL -> RESYNCING -> NORMAL:
 *    al detectar un gap se descartan los eventos WS hasta que el snapshot
 *    REST de /api/status complete, evitando mezclar eventos WS con el snapshot.
 *
 * El backend emite un `sequence` GLOBAL (orden total), por lo que dos eventos
 * consecutivos del mismo topico pueden saltar varios numeros (los intermedios
 * son de otros topicos). La deteccion de gaps se delega en
 * createSequenceTracker(), que evalua el salto contra la marca de agua global
 * (maximo sequence visto en cualquier topico), evitando gaps aparentes.
 */

import { createSignal, onCleanup } from "solid-js";
import { ServerMessageSchema, SystemStatusSchema } from "@/schemas/ws";
import type { ClientMessage, ServerMessage } from "@/types/api";
import { createSequenceTracker } from "@/hooks/sequenceTracker";

const WS_URL = `${location.protocol === "https:" ? "wss:" : "ws:"}//${location.host}/ws`;
const RECONNECT_DELAY = 2000;

// En SECURITY_MODE=protected el backend exige autenticacion en /ws para
// clientes no-loopback. El navegador envia la cookie de sesion HttpOnly
// automaticamente en el handshake (mismo origen). Solo se anuncia el
// subprotocolo "rpi-hmi" para que el backend lo seleccione.
const WS_PROTOCOLS = ["rpi-hmi"];

type SyncState = "normal" | "resyncing";

export function useWebSocket(onMessage: (msg: ServerMessage) => void) {
  const [connected, setConnected] = createSignal(false);
  let ws: WebSocket | null = null;
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  let shouldReconnect = true;
  const tracker = createSequenceTracker();
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
      tracker.reset();
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
      ws = new WebSocket(WS_URL, WS_PROTOCOLS);
    } catch {
      scheduleReconnect();
      return;
    }

    ws.onopen = () => {
      setConnected(true);
      // Nueva conexion: re-baseline de secuencia y estado de sincronizacion.
      tracker.reset();
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

        // Sequence tracking: detectar gaps reales comparando contra la marca de
        // agua global (maximo sequence visto en cualquier topico). Evita gaps
        // aparentes del sequence global compartido entre topicos.
        if (tracker.track(msg.type, msg.sequence)) {
          console.warn(
            `useWebSocket: gap detectado (type=${msg.type}, current=${msg.sequence}), resync...`,
          );
          syncState = "resyncing";
          void resync();
          return;
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

  function reconnect() {
    shouldReconnect = true;
    if (reconnectTimer) {
      clearTimeout(reconnectTimer);
      reconnectTimer = null;
    }
    if (ws) {
      ws.onclose = null;
      ws.close();
      ws = null;
    }
    setConnected(false);
    connect();
  }

  // Auto-connect
  connect();

  onCleanup(disconnect);

  return {
    connected,
    send,
    disconnect,
    reconnect,
  };
}
