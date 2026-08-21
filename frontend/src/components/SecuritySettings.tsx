/**
 * SecuritySettings — Gestion de la contrasena del panel web.
 *
 * Permite:
 *  - Activar/desactivar la contrasena del panel (flag persistido en SQLite).
 *  - Cambiar la contrasena (actual + nueva + confirmar).
 *
 * El estado actual (activada/desactivada y si es la de fabrica "1234") se
 * carga desde GET /api/auth/security al montar. Para activar la contrasena
 * estando desactivada se exige introducir la contrasena actual (no hay cookie
 * de sesion valida en ese caso); para desactivarla, la cookie de sesion del
 * panel autoriza el cambio.
 */

import { createSignal, onMount, Show } from "solid-js";
import type { SecurityStatus } from "@/types/api";
import { useApi } from "@/hooks/useApi";

interface SecuritySettingsProps {
  onBack: () => void;
}

export function SecuritySettings(props: SecuritySettingsProps) {
  const api = useApi();

  const [loading, setLoading] = createSignal(true);
  const [status, setStatus] = createSignal<SecurityStatus | null>(null);
  const [message, setMessage] = createSignal<string | null>(null);
  const [error, setError] = createSignal<string | null>(null);

  // Toggle activar/desactivar
  const [currentForToggle, setCurrentForToggle] = createSignal("");
  const [toggling, setToggling] = createSignal(false);

  // Cambio de contrasena
  const [currentPwd, setCurrentPwd] = createSignal("");
  const [newPwd, setNewPwd] = createSignal("");
  const [confirmPwd, setConfirmPwd] = createSignal("");
  const [changing, setChanging] = createSignal(false);

  onMount(async () => {
    const s = await api.getSecurity();
    if (s) setStatus(s);
    setLoading(false);
  });

  function clearFeedback() {
    setMessage(null);
    setError(null);
  }

  async function toggleSecurity() {
    clearFeedback();
    const enabled = status()?.enabled ?? false;
    const target = !enabled;

    // Para activar (no hay sesion valida) se exige la contrasena actual.
    if (target && !currentForToggle()) {
      setError("Introduce la contrasena actual para activar");
      return;
    }

    setToggling(true);
    const r = await api.setSecurityEnabled(target, currentForToggle() || undefined);
    setToggling(false);

    if (r) {
      setStatus(r);
      setCurrentForToggle("");
      setMessage(target ? "Contrasena activada" : "Contrasena desactivada");
    } else {
      setError("No se pudo cambiar el estado de la contrasena");
    }
  }

  async function changePassword() {
    clearFeedback();
    if (!currentPwd()) {
      setError("Introduce la contrasena actual");
      return;
    }
    if (newPwd().length < 4) {
      setError("La nueva contrasena debe tener al menos 4 caracteres");
      return;
    }
    if (newPwd() !== confirmPwd()) {
      setError("La nueva contrasena no coincide con la confirmacion");
      return;
    }

    setChanging(true);
    const r = await api.changePassword(currentPwd(), newPwd());
    setChanging(false);

    if (r?.success) {
      setCurrentPwd("");
      setNewPwd("");
      setConfirmPwd("");
      const s = await api.getSecurity();
      if (s) setStatus(s);
      setMessage("Contrasena actualizada. Vuelve a iniciar sesion.");
    } else {
      setError("No se pudo cambiar la contrasena (verifica la contrasena actual)");
    }
  }

  return (
    <div class="min-h-screen flex flex-col items-center justify-center bg-[#141428] p-6">
      <div class="bg-[#0f0f23] border border-[#2a2a5e] rounded-2xl p-8 w-[420px] max-w-[94vw] shadow-2xl">
        <h2 class="text-xl font-bold text-gray-200 mb-6 text-center tracking-wider">
          CONTRASENA
        </h2>

        <Show when={loading()}>
          <div class="text-gray-500 text-center py-8">Cargando seguridad...</div>
        </Show>

        <Show when={!loading()}>
          {/* Estado actual */}
          <div class="bg-[#1a1a3e] rounded-lg p-4 mb-6 text-sm space-y-2">
            <div class="flex items-center justify-between">
              <span class="text-gray-500">Estado</span>
              <span
                class="font-semibold"
                classList={{
                  "text-[#4aef9e]": status()?.enabled,
                  "text-gray-400": !status()?.enabled,
                }}
              >
                {status()?.enabled ? "Activada" : "Desactivada"}
              </span>
            </div>
            <div class="flex items-center justify-between">
              <span class="text-gray-500">Contrasena</span>
              <span
                class="font-semibold"
                classList={{
                  "text-[#ffb84a]": status()?.is_default,
                  "text-gray-300": !status()?.is_default,
                }}
              >
                {status()?.is_default ? "De fabrica (1234)" : "Personalizada"}
              </span>
            </div>
          </div>

          <Show when={message()}>
            <div class="bg-emerald-900/40 border border-emerald-600/50 text-emerald-300 text-sm rounded-lg px-4 py-2 mb-4">
              {message()}
            </div>
          </Show>

          <Show when={error()}>
            <div class="bg-red-900/40 border border-red-600/50 text-red-300 text-sm rounded-lg px-4 py-2 mb-4">
              {error()}
            </div>
          </Show>

          {/* Toggle activar/desactivar */}
          <div class="mb-8">
            <div class="text-gray-500 text-xs font-semibold mb-2 tracking-wider">
              ACTIVAR / DESACTIVAR
            </div>

            <Show when={!status()?.enabled}>
              <Field
                label="Contrasena actual"
                value={currentForToggle()}
                onChange={setCurrentForToggle}
                placeholder="1234"
                type="password"
              />
            </Show>

            <button
              onClick={toggleSecurity}
              disabled={toggling()}
              class="w-full py-3 rounded-xl font-bold text-sm transition-colors
                     disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
              classList={{
                "bg-[#e94560] hover:bg-[#f05a74] text-white": status()?.enabled,
                "bg-[#0f3460] hover:bg-[#1a4a7a] text-white": !status()?.enabled,
              }}
            >
              {toggling()
                ? "Aplicando..."
                : status()?.enabled
                  ? "Desactivar contrasena"
                  : "Activar contrasena"}
            </button>
          </div>

          {/* Cambio de contrasena */}
          <div>
            <div class="text-gray-500 text-xs font-semibold mb-2 tracking-wider">
              CAMBIAR CONTRASENA
            </div>
            <div class="space-y-3">
              <Field
                label="Contrasena actual"
                value={currentPwd()}
                onChange={setCurrentPwd}
                placeholder="Contrasena actual"
                type="password"
              />
              <Field
                label="Nueva contrasena"
                value={newPwd()}
                onChange={setNewPwd}
                placeholder="Minimo 4 caracteres"
                type="password"
              />
              <Field
                label="Confirmar nueva contrasena"
                value={confirmPwd()}
                onChange={setConfirmPwd}
                placeholder="Repite la nueva contrasena"
                type="password"
              />
            </div>

            <button
              onClick={changePassword}
              disabled={changing()}
              class="w-full mt-4 py-3 rounded-xl bg-[#e94560] hover:bg-[#f05a74] active:bg-[#c23952]
                     text-white font-bold text-sm transition-colors
                     disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
            >
              {changing() ? "Cambiando..." : "Cambiar contrasena"}
            </button>
          </div>

          <button
            onClick={props.onBack}
            class="w-full mt-6 py-3 rounded-xl bg-[#141428] hover:bg-[#1e1e3a]
                   border border-[#1a1a3e] text-gray-400 font-bold text-sm
                   transition-colors cursor-pointer"
          >
            Volver
          </button>
        </Show>
      </div>
    </div>
  );
}

function Field(props: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  type?: string;
}) {
  return (
    <label class="block">
      <span class="text-gray-500 text-xs mb-1 block">{props.label}</span>
      <input
        type={props.type ?? "text"}
        value={props.value}
        onInput={(e) => props.onChange(e.currentTarget.value)}
        placeholder={props.placeholder}
        class="w-full bg-[#1a1a3e] border border-[#2a2a5e] rounded-lg px-3 py-2
               text-gray-200 font-mono text-sm focus:outline-none focus:border-[#e94560]"
      />
    </label>
  );
}
