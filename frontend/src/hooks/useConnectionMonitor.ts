/**
 * useConnectionMonitor — Polling REST de fallback.
 * Mientras el WebSocket este conectado no hace nada; si no, consulta el
 * estado via REST cada 5s y propaga el resultado.
 */

import { onCleanup } from "solid-js";
import type { SystemStatus } from "@/types/api";

interface ConnectionMonitorOptions {
  /** Accessor de senal que indica si el WebSocket esta conectado. */
  isConnected: () => boolean;
  /** Consulta REST que devuelve el estado del sistema o null en caso de error. */
  getStatus: () => Promise<SystemStatus | null>;
  /** Callback que aplica el estado obtenido. */
  onStatus: (status: SystemStatus) => void;
}

export function useConnectionMonitor({
  isConnected,
  getStatus,
  onStatus,
}: ConnectionMonitorOptions) {
  const interval = setInterval(async () => {
    if (isConnected()) return; // WS activo, no poll
    const status = await getStatus();
    if (status) {
      onStatus(status);
    }
  }, 5000);

  onCleanup(() => clearInterval(interval));
}
