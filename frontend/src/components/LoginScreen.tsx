/**
 * LoginScreen — Pantalla de autenticacion del panel web.
 *
 * Se muestra en SECURITY_MODE=protected cuando el backend rechaza la
 * peticion (401) o el WebSocket (4401) por no tener una cookie de sesion
 * valida. La clave introducida se envia a POST /api/auth/login y no se
 * guarda en el navegador: el backend responde con una cookie HttpOnly.
 */

import { createSignal } from "solid-js";

interface LoginScreenProps {
  error: string | null;
  onLogin: (apiKey: string) => Promise<void>;
}

export function LoginScreen(props: LoginScreenProps) {
  const [apiKey, setApiKey] = createSignal("");
  const [busy, setBusy] = createSignal(false);

  async function submit(e: Event) {
    e.preventDefault();
    if (!apiKey() || busy()) return;
    setBusy(true);
    try {
      await props.onLogin(apiKey());
      setApiKey("");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div class="min-h-screen flex items-center justify-center bg-[#141428] p-6">
      <form
        onSubmit={submit}
        class="bg-[#0f0f23] border border-[#2a2a5e] rounded-2xl p-8 w-[380px] max-w-[90vw] shadow-2xl shadow-black/50"
      >
        <div class="flex items-center justify-center gap-3 mb-2">
          <svg
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="1.5"
            stroke-linecap="round"
            stroke-linejoin="round"
            class="w-8 h-8 text-[#e94560]"
          >
            <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
            <path d="M7 11V7a5 5 0 0 1 10 0v4" />
          </svg>
          <h2 class="text-xl font-bold text-gray-200 tracking-wider">
            ACCESO RESTRINGIDO
          </h2>
        </div>

        <p class="text-gray-500 text-xs text-center mb-8">
          Introduce la clave de administracion para controlar el HMI.
        </p>

        <input
          type="password"
          value={apiKey()}
          onInput={(e) => setApiKey(e.currentTarget.value)}
          placeholder="Clave de administracion"
          autocomplete="current-password"
          class="w-full px-4 py-3 rounded-xl bg-[#141428] border border-[#2a2a5e]
                 text-gray-200 placeholder-gray-600 text-sm
                 focus:outline-none focus:ring-2 focus:ring-[#e94560]/50
                 focus:border-[#e94560]/50 transition-all duration-200"
        />

        {props.error && (
          <p class="text-red-500 text-xs mt-3 text-center">{props.error}</p>
        )}

        <button
          type="submit"
          disabled={busy() || !apiKey()}
          class="w-full mt-6 px-6 py-3 rounded-xl font-semibold text-sm tracking-wider
                 bg-[#e94560] hover:bg-[#ff5f78] text-white
                 disabled:opacity-40 disabled:cursor-not-allowed
                 transition-all duration-200
                 focus:outline-none focus:ring-2 focus:ring-[#e94560]/50"
        >
          {busy() ? "Verificando..." : "Entrar"}
        </button>
      </form>
    </div>
  );
}
