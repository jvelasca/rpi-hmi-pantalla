/**
 * App — Componente raiz. Orquesta WebSocket, estado y layout.
 */

import { createEffect, createSignal, onMount, Show } from "solid-js";
import { useApi } from "@/hooks/useApi";
import { useWebSocket } from "@/hooks/useWebSocket";
import { useConnectionMonitor } from "@/hooks/useConnectionMonitor";
import { Header } from "@/components/Header";
import { LedPanel } from "@/components/LedPanel";
import { ButtonPanel } from "@/components/ButtonPanel";
import { ConnectionStatus } from "@/components/ConnectionStatus";
import { ConfigPanel } from "@/components/ConfigPanel";
import { ConfigScreen } from "@/components/ConfigScreen";
import { LoginScreen } from "@/components/LoginScreen";
import { ScreenTest } from "@/components/ScreenTest";
import { TouchCalibration } from "@/components/TouchCalibration";
import { NetworkConfig } from "@/components/NetworkConfig";
import { FontSettings } from "@/components/FontSettings";
import { SecuritySettings } from "@/components/SecuritySettings";
import type { LedState, ButtonState, DisplayAction, ServerMessage } from "@/types/api";

type View =
  | "main"
  | "config"
  | "screenTest"
  | "touchCalibration"
  | "network"
  | "font"
  | "security";

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

  // ── Autenticacion (session-cookie HttpOnly) ─────────
  const [securityMode, setSecurityMode] = createSignal<"local" | "protected" | null>(null);
  const [authenticated, setAuthenticated] = createSignal(false);
  const [loginError, setLoginError] = createSignal<string | null>(null);

  onMount(async () => {
    const status = await api.getAuthStatus();
    if (status) {
      setSecurityMode(status.security_mode);
      setAuthenticated(status.authenticated);
    }
  });

  // Si el backend responde 401 en algun mutador, forzamos el login.
  createEffect(() => {
    if (api.unauthorized()) {
      setAuthenticated(false);
      setSecurityMode("protected");
    }
  });

  async function handleLogin(password: string) {
    setLoginError(null);
    const result = await api.login(password);
    if (result?.authenticated) {
      setAuthenticated(true);
      setSecurityMode("protected");
      ws.reconnect();
    } else {
      setLoginError("Contrasena incorrecta");
    }
  }

  async function handleLogout() {
    await api.logout();
    setAuthenticated(false);
    setLoginError(null);
    ws.disconnect();
  }

  const needsLogin = () => securityMode() === "protected" && !authenticated();

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
  useConnectionMonitor({
    isConnected: ws.connected,
    getStatus: api.getStatus,
    onStatus: (status) => {
      setLed(status.led);
      setButton(status.button);
    },
  });

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

  async function releaseButton() {
    if (ws.connected()) {
      ws.send({ type: "release_button", version: "1.0" });
      return;
    }
    const result = await api.releaseButton();
    if (result) setButton(result);
  }

  // ── Control del display fisico desde el panel web ──
  function commandDisplay(action: DisplayAction) {
    if (ws.connected()) {
      ws.send({ type: "display_command", action, version: "1.0" });
    } else {
      api.sendDisplayCommand(action);
    }
  }

  function goScreenTest() {
    setView("screenTest");
    commandDisplay("screen_test");
  }

  function goTouchCalibration() {
    setView("touchCalibration");
    commandDisplay("touch_calib");
  }

  function goNetwork() {
    setView("network");
    commandDisplay("network");
  }

  function goFont() {
    setView("font");
    commandDisplay("font");
  }

  function goSecurity() {
    setView("security");
  }

  function goBackToMain() {
    setView("main");
    commandDisplay("main");
  }

  // ── Render ──────────────────────────────────────────
  return (
    <div class="min-h-screen flex flex-col bg-[#141428]">
      {/* Pantalla de login: solo en protected y sin sesion valida. */}
      <Show when={needsLogin()}>
        <LoginScreen error={loginError()} onLogin={handleLogin} />
      </Show>

      <Show when={!needsLogin()}>
        <Show when={view() === "screenTest"}>
          <ScreenTest onBack={() => setView("config")} />
        </Show>

        <Show when={view() === "touchCalibration"}>
          <TouchCalibration onBack={() => setView("config")} />
        </Show>

        <Show when={view() === "network"}>
          <NetworkConfig onBack={() => setView("config")} />
        </Show>

        <Show when={view() === "font"}>
          <FontSettings onBack={() => setView("config")} />
        </Show>

        <Show when={view() === "security"}>
          <SecuritySettings onBack={() => setView("config")} />
        </Show>

        <Show when={view() === "main" || view() === "config"}>
          <Header
            connected={ws.connected()}
            wsClients={wsClients()}
            authenticated={authenticated()}
            onLogout={handleLogout}
          />

          <main class="flex-1 flex items-center justify-center p-6">
            <div class="flex flex-wrap gap-6 justify-center items-start">
              <LedPanel led={led()} onToggle={toggleLed} />
              <ButtonPanel button={button()} onPress={pressButton} onRelease={releaseButton} />
            </div>
          </main>

          <ConnectionStatus connected={ws.connected()} error={api.error()} />

          {/* Boton de configuracion */}
          <ConfigPanel onOpen={() => setView("config")} />

          {/* Modal de configuracion */}
          <Show when={view() === "config"}>
            <ConfigScreen
              onScreenTest={goScreenTest}
              onTouchCalibration={goTouchCalibration}
              onNetwork={goNetwork}
              onFont={goFont}
              onSecurity={goSecurity}
              onBack={goBackToMain}
            />
          </Show>
        </Show>
      </Show>
    </div>
  );
}
