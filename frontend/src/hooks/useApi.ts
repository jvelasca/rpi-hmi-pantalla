/**
 * useApi — REST client para el backend FastAPI.
 * Fallback cuando WebSocket no esta disponible.
 *
 * La autenticacion del panel web se gestiona con una cookie de sesion HttpOnly
 * (emitida por POST /api/auth/login). El navegador envia la cookie
 * automaticamente en cada fetch; no se maneja ninguna API key en JS.
 */

import { createSignal } from "solid-js";
import type {
  ButtonState,
  DisplayAction,
  DisplaySettings,
  LedState,
  NetworkResult,
  NetworkStatus,
  SecurityStatus,
  SystemStatus,
} from "@/types/api";

const BASE = "/api";

export interface AuthStatus {
  security_enabled: boolean;
  authenticated: boolean;
}

export function useApi() {
  const [error, setError] = createSignal<string | null>(null);
  const [unauthorized, setUnauthorized] = createSignal(false);

  async function handle<T>(res: Response): Promise<T | null> {
    if (res.status === 401) setUnauthorized(true);
    if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
    setError(null);
    return (await res.json()) as T;
  }

  async function get<T>(endpoint: string): Promise<T | null> {
    try {
      const res = await fetch(`${BASE}${endpoint}`, {
        headers: { Accept: "application/json" },
        credentials: "include",
        signal: AbortSignal.timeout(3000),
      });
      return await handle<T>(res);
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
        headers: {
          Accept: "application/json",
          "Content-Type": "application/json",
        },
        body: body !== undefined ? JSON.stringify(body) : undefined,
        credentials: "include",
        signal: AbortSignal.timeout(5000),
      });
      return await handle<T>(res);
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
  const sendDisplayCommand = (action: DisplayAction) =>
    postJson<{ success: boolean; action: string }>("/display/command", { action });

  const getAuthStatus = () => get<AuthStatus>("/auth/status");
  const login = (password: string) =>
    postJson<{ authenticated: boolean }>("/auth/login", { password });
  const logout = () => postJson<{ authenticated: boolean }>("/auth/logout");

  const getSecurity = () => get<SecurityStatus>("/auth/security");
  const setSecurityEnabled = (enabled: boolean, current?: string) =>
    postJson<SecurityStatus>("/auth/security", { enabled, current: current ?? null });
  const changePassword = (current: string, next: string) =>
    postJson<{ success: boolean }>("/auth/password", { current, new: next });

  return {
    error,
    unauthorized,
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
    getAuthStatus,
    login,
    logout,
    getSecurity,
    setSecurityEnabled,
    changePassword,
  };
}
