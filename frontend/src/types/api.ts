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

/** Estado de la red (GET /api/network) */
export interface NetworkStatus {
  interface: string; // "eth0"
  connection_name: string; // "Wired connection 1"
  mode: "dhcp" | "static";
  ip_address: string | null;
  prefix: number | null; // 0-32
  gateway: string | null;
  dns: string | null;
}

/** Resultado de aplicar configuracion de red */
export interface NetworkResult {
  success: boolean;
  message: string;
  status: NetworkStatus | null;
}

/** Ajustes visuales del display fisico (fuente y tamano de texto) */
export interface DisplaySettings {
  font_family: "dejavu" | "liberation";
  text_size: "small" | "medium" | "large";
}

/** Accion de cambio de vista enviada al display fisico */
export type DisplayAction =
  | "screen_test"
  | "touch_calib"
  | "network"
  | "font"
  | "config"
  | "main";

/** Estado de seguridad del panel web (GET /api/auth/security) */
export interface SecurityStatus {
  enabled: boolean; // contraseña del panel activada
  is_default: boolean; // la contraseña es la de fabrica (1234)
}

// ── WebSocket messages ──────────────────────────────

export type WsTopic = "led" | "button" | "display" | "system";

export type ClientMessage =
  | { type: "toggle_led"; version: string }
  | { type: "press_button"; version: string }
  | { type: "release_button"; version: string }
  | { type: "get_status"; version: string }
  | { type: "display_command"; action: DisplayAction; version: string }
  | { type: "subscribe"; topics: WsTopic[]; version: string };

export type ServerMessage =
  | { type: "status_update"; data: SystemStatus; timestamp: string; version: string; sequence: number | null }
  | { type: "led_changed"; data: LedState; timestamp: string; version: string; sequence: number | null }
  | { type: "button_pressed"; data: ButtonState; timestamp: string; version: string; sequence: number | null }
  | { type: "button_released"; data: ButtonState; timestamp: string; version: string; sequence: number | null }
  | { type: "display_changed"; data: DisplayInfo; timestamp: string; version: string; sequence: number | null }
  | { type: "display_command"; data: { action: DisplayAction }; timestamp: string; version: string; sequence: number | null }
  | { type: "display_settings_changed"; data: DisplaySettings; timestamp: string; version: string; sequence: number | null }
  | { type: "error"; data: { code: string; message: string }; timestamp: string; version: string; sequence: number | null };
