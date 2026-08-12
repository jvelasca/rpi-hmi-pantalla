/**
 * Tests para hooks del frontend RPi HMI.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { createRoot, createSignal } from "solid-js";

// ── Mock global fetch ───────────────────────────────────────────

const mockFetch = vi.fn();
vi.stubGlobal("fetch", mockFetch);

beforeEach(() => {
  mockFetch.mockReset();
});

// ── useApi Tests ────────────────────────────────────────────────

describe("useApi", () => {
  it("getStatus devuelve SystemStatus en llamada exitosa", async () => {
    const { useApi } = await import("@/hooks/useApi");

    const mockStatus = {
      led: { state: false, label: "APAGADO", gpio_pin: 17 },
      button: { pressed: false, press_count: 0 },
      display: null,
      uptime_seconds: 123.4,
      cpu_temp_celsius: null,
      websocket_clients: 0,
      timestamp: "2026-01-01T00:00:00Z",
    };

    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(mockStatus),
    });

    let result: unknown = null;
    const dispose = createRoot((disposer) => {
      const api = useApi();
      api.getStatus().then((r) => {
        result = r;
        disposer();
      });
      return disposer;
    });

    await vi.waitFor(() => {
      expect(result).not.toBeNull();
    });

    const status = result as Record<string, unknown>;
    expect(status.led).toBeDefined();
    expect(status.button).toBeDefined();
    expect(status.uptime_seconds).toBe(123.4);

    const [url, opts] = mockFetch.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/status");
    expect(opts.headers).toEqual({ Accept: "application/json" });
  });

  it("toggleLed llama a POST /api/led/toggle", async () => {
    const { useApi } = await import("@/hooks/useApi");

    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve({ state: true, label: "ENCENDIDO", gpio_pin: 17 }),
    });

    let result: unknown = null;
    createRoot((disposer) => {
      const api = useApi();
      api.toggleLed().then((r) => {
        result = r;
        disposer();
      });
    });

    await vi.waitFor(() => {
      expect(result).not.toBeNull();
    });

    const [url, opts] = mockFetch.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/led/toggle");
    expect(opts.method).toBe("POST");
  });

  it("pressButton llama a POST /api/button/press", async () => {
    const { useApi } = await import("@/hooks/useApi");

    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve({ pressed: true, press_count: 1 }),
    });

    let result: unknown = null;
    createRoot((disposer) => {
      const api = useApi();
      api.pressButton().then((r) => {
        result = r;
        disposer();
      });
    });

    await vi.waitFor(() => {
      expect(result).not.toBeNull();
    });

    const btn = result as Record<string, unknown>;
    expect(btn.pressed).toBe(true);
    expect(btn.press_count).toBe(1);
  });

  it("retorna null y establece error en fetch fallido", async () => {
    const { useApi } = await import("@/hooks/useApi");

    mockFetch.mockRejectedValueOnce(new Error("Network error"));

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    let apiRef: Record<string, any> | null = null;
    let result: unknown = "not-null";
    createRoot((disposer) => {
      apiRef = useApi();
      apiRef.getStatus().then((r: unknown) => {
        result = r;
        disposer();
      });
    });

    await vi.waitFor(() => {
      expect(result).toBeNull();
    });

    expect(apiRef!.error()).not.toBeNull();
    expect(apiRef!.error()).toContain("Network error");
  });

  it("retorna null en respuesta HTTP no ok", async () => {
    const { useApi } = await import("@/hooks/useApi");

    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 500,
      statusText: "Internal Server Error",
    });

    let result: unknown = "not-null";
    createRoot((disposer) => {
      const api = useApi();
      api.getStatus().then((r: unknown) => {
        result = r;
        disposer();
      });
    });

    await vi.waitFor(() => {
      expect(result).toBeNull();
    });
  });

  it("leadOn llama a POST /api/led/on", async () => {
    const { useApi } = await import("@/hooks/useApi");

    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve({ state: true, label: "ENCENDIDO", gpio_pin: 17 }),
    });

    let result: unknown = null;
    createRoot((disposer) => {
      const api = useApi();
      api.ledOn().then((r) => {
        result = r;
        disposer();
      });
    });

    await vi.waitFor(() => {
      expect(result).not.toBeNull();
    });

    const [url, opts] = mockFetch.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/led/on");
    expect(opts.method).toBe("POST");
  });

  it("ledOff llama a POST /api/led/off", async () => {
    const { useApi } = await import("@/hooks/useApi");

    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve({ state: false, label: "APAGADO", gpio_pin: 17 }),
    });

    let result: unknown = null;
    createRoot((disposer) => {
      const api = useApi();
      api.ledOff().then((r) => {
        result = r;
        disposer();
      });
    });

    await vi.waitFor(() => {
      expect(result).not.toBeNull();
    });

    const [url, opts] = mockFetch.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/led/off");
    expect(opts.method).toBe("POST");
  });
});

// ── Type-Level Tests ───────────────────────────────────────────

describe("API types contract", () => {
  it("LedState tiene campos requeridos", () => {
    // Verificacion en tiempo de compilacion via type assertion
    const led: import("@/types/api").LedState = {
      state: true,
      label: "ENCENDIDO",
      gpio_pin: 17,
    };
    expect(led.state).toBe(true);
    expect(led.label).toBe("ENCENDIDO");
    expect(led.gpio_pin).toBe(17);
  });

  it("ButtonState tiene campos requeridos", () => {
    const btn: import("@/types/api").ButtonState = {
      pressed: false,
      press_count: 0,
    };
    expect(btn.pressed).toBe(false);
    expect(btn.press_count).toBe(0);
  });

  it("SystemStatus tiene todos los subsistemas", () => {
    const status: import("@/types/api").SystemStatus = {
      led: { state: false, label: "APAGADO", gpio_pin: 17 },
      button: { pressed: false, press_count: 0 },
      display: null,
      uptime_seconds: 0,
      cpu_temp_celsius: null,
      websocket_clients: 0,
      timestamp: "2026-01-01T00:00:00Z",
    };
    expect(status.led).toBeDefined();
    expect(status.button).toBeDefined();
    expect(status.uptime_seconds).toBe(0);
  });
});

// ── useWebSocket Tests ──────────────────────────────────────────

describe("useWebSocket", () => {
  it("devuelve las funciones connected y send tras inicializar", async () => {
    const { useWebSocket } = await import("@/hooks/useWebSocket");
    const onMsg = vi.fn();

    let hookResult: ReturnType<typeof useWebSocket> | null = null;
    createRoot((disposer) => {
      hookResult = useWebSocket(onMsg);
    });

    expect(hookResult).not.toBeNull();
    expect(typeof hookResult!.send).toBe("function");
    expect(typeof hookResult!.connected).toBe("function");
    expect(typeof hookResult!.disconnect).toBe("function");
  });
});
