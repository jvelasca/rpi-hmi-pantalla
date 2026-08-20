/**
 * Esquemas Zod para validacion runtime de mensajes WebSocket.
 *
 * Reflejan los modelos Pydantic del backend (backend/app/models/events.py):
 *  - `sequence` es `number | null` (None en el backend, p. ej. status_update y error).
 *  - `data` es el payload especifico de cada tipo de evento.
 */

import { z } from "zod";

// ── Payloads ──────────────────────────────────────────────────

export const LedStateSchema = z.object({
  state: z.boolean(),
  label: z.string(),
  gpio_pin: z.number().int(),
});

export const ButtonStateSchema = z.object({
  pressed: z.boolean(),
  press_count: z.number().int().nonnegative(),
});

export const DisplayInfoSchema = z.object({
  connected: z.boolean(),
  resolution: z.string(),
  driver: z.string(),
});

export const SystemStatusSchema = z.object({
  led: LedStateSchema,
  button: ButtonStateSchema,
  display: DisplayInfoSchema.nullable(),
  uptime_seconds: z.number().nonnegative(),
  cpu_temp_celsius: z.number().nullable(),
  websocket_clients: z.number().int().nonnegative(),
  timestamp: z.string(),
});

export const DisplaySettingsSchema = z.object({
  font_family: z.enum(["dejavu", "liberation"]),
  text_size: z.enum(["small", "medium", "large"]),
});

export const ErrorDetailSchema = z.object({
  code: z.string(),
  message: z.string(),
});

export const DisplayCommandDataSchema = z.object({
  action: z.string(),
});

// ── Mensajes Servidor -> Cliente ──────────────────────────────

const serverMessageBase = {
  timestamp: z.string(),
  version: z.string(),
  sequence: z.number().int().nonnegative().nullable(),
};

export const ServerMessageSchema = z.discriminatedUnion("type", [
  z.object({ ...serverMessageBase, type: z.literal("status_update"), data: SystemStatusSchema }),
  z.object({ ...serverMessageBase, type: z.literal("led_changed"), data: LedStateSchema }),
  z.object({ ...serverMessageBase, type: z.literal("button_pressed"), data: ButtonStateSchema }),
  z.object({ ...serverMessageBase, type: z.literal("button_released"), data: ButtonStateSchema }),
  z.object({ ...serverMessageBase, type: z.literal("display_changed"), data: DisplayInfoSchema }),
  z.object({ ...serverMessageBase, type: z.literal("display_command"), data: DisplayCommandDataSchema }),
  z.object({ ...serverMessageBase, type: z.literal("display_settings_changed"), data: DisplaySettingsSchema }),
  z.object({ ...serverMessageBase, type: z.literal("error"), data: ErrorDetailSchema }),
]);

// ── Mensajes Cliente -> Servidor ──────────────────────────────

export const WsTopicSchema = z.enum(["led", "button", "display", "system"]);

export const ClientMessageSchema = z.discriminatedUnion("type", [
  z.object({ type: z.literal("toggle_led"), version: z.string() }),
  z.object({ type: z.literal("press_button"), version: z.string() }),
  z.object({ type: z.literal("release_button"), version: z.string() }),
  z.object({ type: z.literal("get_status"), version: z.string() }),
  z.object({ type: z.literal("display_command"), action: z.string(), version: z.string() }),
  z.object({ type: z.literal("subscribe"), topics: z.array(WsTopicSchema), version: z.string() }),
]);

// ── Tipos inferidos ───────────────────────────────────────────

export type ParsedServerMessage = z.infer<typeof ServerMessageSchema>;
export type ParsedClientMessage = z.infer<typeof ClientMessageSchema>;
export type ParsedSystemStatus = z.infer<typeof SystemStatusSchema>;
