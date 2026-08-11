/**
 * Tipos TypeScript mirror de los modelos Pydantic del backend.
 * Contrato tipado verificable entre frontend y backend.
 */

/** Estado del LED */
export interface LedState {
  state: boolean; // true = encendido
  label: string; // "ENCENDIDO" | "APAGADO"
  gpio_pin: number; // 2-27
}

/** Estado del boton */
export interface ButtonState {
  pressed: boolean;
  press_count: number; // >= 0
}

/** Informacion del display fisico */
export interface DisplayInfo {
  connected: boolean;
  resolution: string; // "WxH"
  driver: string;
}

/** Estado completo del sistema (GET /api/status) */
export interface SystemStatus {
  led: LedState;
  button: ButtonState;
  display: DisplayInfo | null;
  uptime_seconds: number;
  cpu_temp_celsius: number | null;
  websocket_clients: number; // >= 0
  timestamp: string; // ISO 8601
}

// ── WebSocket messages ──────────────────────────────

export type WsTopic = "led" | "button" | "display" | "system";

export type ClientMessage =
  | { type: "toggle_led"; version: string }
  | { type: "press_button"; version: string }
  | { type: "release_button"; version: string }
  | { type: "get_status"; version: string }
  | { type: "subscribe"; topics: WsTopic[]; version: string };

export type ServerMessage =
  | { type: "status_update"; data: SystemStatus; timestamp: string; version: string }
  | { type: "led_changed"; data: LedState; timestamp: string; version: string }
  | { type: "button_pressed"; data: ButtonState; timestamp: string; version: string }
  | { type: "button_released"; data: ButtonState; timestamp: string; version: string }
  | { type: "display_changed"; data: DisplayInfo; timestamp: string; version: string }
  | { type: "error"; data: { code: string; message: string }; timestamp: string; version: string };
