/**
 * useApi — REST client para el backend FastAPI.
 * Fallback cuando WebSocket no esta disponible.
 */

import { createSignal } from "solid-js";
import type { ButtonState, LedState, SystemStatus } from "@/types/api";

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
    try {
      const res = await fetch(`${BASE}${endpoint}`, {
        method: "POST",
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

  const getStatus = () => get<SystemStatus>("/status");
  const getLed = () => get<LedState>("/led");
  const toggleLed = () => post<LedState>("/led/toggle");
  const ledOn = () => post<LedState>("/led/on");
  const ledOff = () => post<LedState>("/led/off");
  const getButton = () => get<ButtonState>("/button");
  const pressButton = () => post<ButtonState>("/button/press");

  return { error, getStatus, getLed, toggleLed, ledOn, ledOff, getButton, pressButton };
}
