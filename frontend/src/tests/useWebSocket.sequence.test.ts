/**
 * Tests para la deteccion de gaps de secuencia WebSocket por-topic
 * (createSequenceTracker).
 */
import { describe, it, expect, vi } from "vitest";
import {
  createSequenceTracker,
  topicForMessageType,
} from "@/hooks/sequenceTracker";

describe("topicForMessageType", () => {
  it("mapea cada type de evento a su topic rastreable", () => {
    expect(topicForMessageType("led_changed")).toBe("led");
    expect(topicForMessageType("button_pressed")).toBe("button");
    expect(topicForMessageType("button_released")).toBe("button");
    expect(topicForMessageType("display_changed")).toBe("display");
    expect(topicForMessageType("display_command")).toBe("display");
    expect(topicForMessageType("display_settings_changed")).toBe("display");
  });

  it("no rastrea status_update ni error", () => {
    expect(topicForMessageType("status_update")).toBeNull();
    expect(topicForMessageType("error")).toBeNull();
  });
});

describe("createSequenceTracker", () => {
  it("sin gap: led 10 -> led 11 no dispara resync", () => {
    const tracker = createSequenceTracker();
    const resync = vi.fn();

    if (tracker.track("led_changed", 10)) resync();
    if (tracker.track("led_changed", 11)) resync();

    expect(resync).not.toHaveBeenCalled();
  });

  it("gap real por-topic: led 10 -> led 12 dispara resync", () => {
    const tracker = createSequenceTracker();
    const resync = vi.fn();

    if (tracker.track("led_changed", 10)) resync();
    if (tracker.track("led_changed", 12)) resync();

    expect(resync).toHaveBeenCalledTimes(1);
  });

  it("gap APARENTE (bug): led 10 -> button 11 -> led 12 NO dispara resync", () => {
    const tracker = createSequenceTracker();
    const resync = vi.fn();

    if (tracker.track("led_changed", 10)) resync();
    if (tracker.track("button_pressed", 11)) resync();
    if (tracker.track("led_changed", 12)) resync();

    expect(resync).not.toHaveBeenCalled();
  });

  it("resetea el baseline tras reset() (onopen/resync)", () => {
    const tracker = createSequenceTracker();
    const resync = vi.fn();

    if (tracker.track("led_changed", 10)) resync();
    tracker.reset();

    // Sin reset, led 12 tras led 10 seria gap; tras reset es nuevo baseline.
    if (tracker.track("led_changed", 12)) resync();

    expect(resync).not.toHaveBeenCalled();
  });

  it("ignora mensajes sin sequence numerico o topic no rastreable", () => {
    const tracker = createSequenceTracker();
    const resync = vi.fn();

    if (tracker.track("status_update", null)) resync();
    if (tracker.track("error", null)) resync();
    if (tracker.track("led_changed", null)) resync();

    expect(resync).not.toHaveBeenCalled();
  });
});
