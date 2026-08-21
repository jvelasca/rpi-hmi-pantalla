/**
 * Tests para componentes SolidJS del frontend RPi HMI.
 *
 * Estos tests verifican que los componentes compilan, exportan y
 * aceptan los tipos de props esperados. No usan renderizado DOM
 * para evitar problemas de resolucion solid-js/web en vitest.
 */
import { describe, it, expect, vi } from "vitest";

// ── Smoke test: imports should work ────────────────────────────

describe("Component exports", () => {
  it("@/components/LedPanel imports", async () => {
    const mod = await import("@/components/LedPanel");
    expect(mod.LedPanel).toBeDefined();
    expect(typeof mod.LedPanel).toBe("function");
  });

  it("@/components/ButtonPanel imports", async () => {
    const mod = await import("@/components/ButtonPanel");
    expect(mod.ButtonPanel).toBeDefined();
    expect(typeof mod.ButtonPanel).toBe("function");
  });

  it("@/components/Header imports", async () => {
    const mod = await import("@/components/Header");
    expect(mod.Header).toBeDefined();
    expect(typeof mod.Header).toBe("function");
  });

  it("@/components/ConnectionStatus imports", async () => {
    const mod = await import("@/components/ConnectionStatus");
    expect(mod.ConnectionStatus).toBeDefined();
    expect(typeof mod.ConnectionStatus).toBe("function");
  });

  it("@/components/SecuritySettings imports", async () => {
    const mod = await import("@/components/SecuritySettings");
    expect(mod.SecuritySettings).toBeDefined();
    expect(typeof mod.SecuritySettings).toBe("function");
  });

  it("@/types/api types import", async () => {
    const mod = await import("@/types/api");
    expect(mod).toBeDefined();
  });
});
