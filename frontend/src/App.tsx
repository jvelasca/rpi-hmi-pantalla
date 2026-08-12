/**
 * App — Componente raiz. Orquesta WebSocket, estado y layout.
 */

import { createSignal, onCleanup, Show } from "solid-js";
import { useApi } from "@/hooks/useApi";
import { useWebSocket } from "@/hooks/useWebSocket";
import { Header } from "@/components/Header";
import { LedPanel } from "@/components/LedPanel";
import { ButtonPanel } from "@/components/ButtonPanel";
import { ConnectionStatus } from "@/components/ConnectionStatus";
import { ConfigPanel } from "@/components/ConfigPanel";
import { ConfigScreen } from "@/components/ConfigScreen";
import { ScreenTest } from "@/components/ScreenTest";
import { TouchCalibration } from "@/components/TouchCalibration";
import type { LedState, ButtonState, ServerMessage } from "@/types/api";

type View = "main" | "config" | "screenTest" | "touchCalibration";

export function App() {
  // ── Estado ──────────────────────────────────────────
  const [led, setLed] = createSignal<LedState>({
    state: false,
    label: "APAGADO",
    gpio_pin: 0, // Se sincroniza con backend
  });
  const [button, setButton] = createSignal<ButtonState>({
    pressed: false,
    press_count: 0,
  });
  const [wsClients, setWsClients] = createSignal(0);

  // ── Navegacion (main, config, screenTest, touchCalibration) ─
  const [view, setView] = createSignal<View>("main");

  // ── API REST (fallback) ─────────────────────────────
  const api = useApi();

  // ── WebSocket ───────────────────────────────────────
  function handleWsMessage(msg: ServerMessage) {
    switch (msg.type) {
      case "status_update":
        setLed(msg.data.led);
        setButton(msg.data.button);
        setWsClients(msg.data.websocket_clients);
        break;
      case "led_changed":
        setLed(msg.data);
        break;
      case "button_pressed":
        setButton(msg.data);
        break;
      case "button_released":
        setButton(msg.data);
        break;
    }
  }

  const ws = useWebSocket(handleWsMessage);

  // ── Poll REST como fallback cada 5s ────────────────
  const pollInterval = setInterval(async () => {
    if (ws.connected()) return; // WS activo, no poll
    const status = await api.getStatus();
    if (status) {
      setLed(status.led);
      setButton(status.button);
    }
  }, 5000);
  onCleanup(() => clearInterval(pollInterval));

  // ── Acciones ────────────────────────────────────────
  async function toggleLed() {
    // Try WS first
    if (ws.connected()) {
      ws.send({ type: "toggle_led", version: "1.0" });
      return;
    }
    // Fallback to REST
    const result = await api.toggleLed();
    if (result) setLed(result);
  }

  async function pressButton() {
    if (ws.connected()) {
      ws.send({ type: "press_button", version: "1.0" });
      return;
    }
    const result = await api.pressButton();
    if (result) setButton(result);
  }

  // ── Render ──────────────────────────────────────────
  return (
    <div class="min-h-screen flex flex-col bg-[#141428]">
      <Show when={view() === "screenTest"}>
        <ScreenTest onBack={() => setView("config")} />
      </Show>

      <Show when={view() === "touchCalibration"}>
        <TouchCalibration onBack={() => setView("config")} />
      </Show>

      <Show when={view() === "main" || view() === "config"}>
        <Header connected={ws.connected()} wsClients={wsClients()} />

        <main class="flex-1 flex items-center justify-center p-6">
          <div class="flex flex-wrap gap-6 justify-center items-start">
            <LedPanel led={led()} onToggle={toggleLed} />
            <ButtonPanel button={button()} onPress={pressButton} />
          </div>
        </main>

        <ConnectionStatus connected={ws.connected()} error={api.error()} />

        {/* Boton de configuracion */}
        <ConfigPanel onOpen={() => setView("config")} />

        {/* Modal de configuracion */}
        <Show when={view() === "config"}>
          <ConfigScreen
            onScreenTest={() => setView("screenTest")}
            onTouchCalibration={() => setView("touchCalibration")}
            onBack={() => setView("main")}
          />
        </Show>
      </Show>
    </div>
  );
}
