/**
 * useApi — REST client para el backend FastAPI.
 * Fallback cuando WebSocket no esta disponible.
 */

import { createSignal } from "solid-js";
import type {
  ButtonState,
  DisplaySettings,
  LedState,
  NetworkResult,
  NetworkStatus,
  SystemStatus,
} from "@/types/api";

const BASE = "/api";

export function useApi() {
  const [error, setError] = createSignal<string | null>(null);

  async function get<T>(endpoint: string): Promise<T | null> {
    try {
      const res = await fetch(`${BASE}${endpoint}`, {
        headers: { Accept: "application/json" },
        signal: AbortSignal.timeout(3000),
      });
      if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
      setError(null);
      return (await res.json()) as T;
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      return null;
    }
  }

  async function post<T>(endpoint: string): Promise<T | null> {
    return postJson<T>(endpoint);
  }

  async function postJson<T>(endpoint: string, body?: unknown): Promise<T | null> {
    try {
      const res = await fetch(`${BASE}${endpoint}`, {
        method: "POST",
        headers: { Accept: "application/json", "Content-Type": "application/json" },
        body: body !== undefined ? JSON.stringify(body) : undefined,
        signal: AbortSignal.timeout(5000),
      });
      if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
      setError(null);
      return (await res.json()) as T;
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      return null;
    }
  }

  const getStatus = () => get<SystemStatus>("/status");
  const getLed = () => get<LedState>("/led");
  const toggleLed = () => post<LedState>("/led/toggle");
  const ledOn = () => post<LedState>("/led/on");
  const ledOff = () => post<LedState>("/led/off");
  const getButton = () => get<ButtonState>("/button");
  const pressButton = () => post<ButtonState>("/button/press");
  const releaseButton = () => post<ButtonState>("/button/release");

  const getNetwork = () => get<NetworkStatus>("/network");
  const applyStatic = (ip: string, prefix: number, gateway: string, dns: string | null) =>
    postJson<NetworkResult>("/network/static", {
      ip_address: ip,
      prefix,
      gateway,
      dns,
    });
  const applyDhcp = () => post<NetworkResult>("/network/dhcp");

  const getDisplaySettings = () => get<DisplaySettings>("/settings/display");
  const setDisplaySettings = (font_family: string, text_size: string) =>
    postJson<DisplaySettings>("/settings/display", { font_family, text_size });
  const sendDisplayCommand = (action: string) =>
    postJson<{ success: boolean; action: string }>("/display/command", { action });

  return {
    error,
    getStatus,
    getLed,
    toggleLed,
    ledOn,
    ledOff,
    getButton,
    pressButton,
    releaseButton,
    getNetwork,
    applyStatic,
    applyDhcp,
    getDisplaySettings,
    setDisplaySettings,
    sendDisplayCommand,
  };
}
