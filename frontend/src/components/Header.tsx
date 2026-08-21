/**
 * Header — Barra superior con titulo y estado de conexion.
 */

import { Show } from "solid-js";

interface HeaderProps {
  connected: boolean;
  wsClients: number;
  authenticated: boolean;
  onLogout: () => void;
}

export function Header(props: HeaderProps) {
  return (
    <header class="bg-[#0f0f23] border-b border-[#1a1a3e] px-6 py-3 flex items-center justify-between">
      <div class="flex items-center gap-3">
        <span class="text-[#e94560] font-bold text-lg tracking-wider">
          RASPBERRY HMI
        </span>
        <span class="text-gray-600 text-xs">v3.0</span>
      </div>

      <div class="flex items-center gap-4">
        {/* Estado display */}
        <span class="text-gray-500 text-xs">Display OK</span>

        {/* WebSocket status */}
        <div class="flex items-center gap-1.5">
          <span
            class="w-2 h-2 rounded-full"
            classList={{
              "bg-green-500 animate-pulse": props.connected,
              "bg-red-500": !props.connected,
            }}
          />
          <span
            class="text-xs font-mono"
            classList={{
              "text-green-500": props.connected,
              "text-red-400": !props.connected,
            }}
          >
            {props.connected ? `WS:${props.wsClients}` : "WS:--"}
          </span>
        </div>

        {/* Cerrar sesion (solo cuando hay sesion activa) */}
        <Show when={props.authenticated}>
          <button
            onClick={props.onLogout}
            class="text-xs text-gray-500 hover:text-[#e94560] transition-colors
                   focus:outline-none focus:ring-2 focus:ring-[#e94560]/50 rounded px-2 py-1"
          >
            Salir
          </button>
        </Show>
      </div>
    </header>
  );
}
