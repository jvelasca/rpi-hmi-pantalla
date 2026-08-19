/**
 * NetworkConfig — Configuracion de IP de la Pi (estatica / DHCP).
 */

import { createSignal, onMount, Show } from "solid-js";
import type { NetworkStatus } from "@/types/api";
import { useApi } from "@/hooks/useApi";

interface NetworkConfigProps {
  onBack: () => void;
}

const IP_RE = /^(25[0-5]|2[0-4]\d|1?\d?\d)(\.(25[0-5]|2[0-4]\d|1?\d?\d)){3}$/;

export function NetworkConfig(props: NetworkConfigProps) {
  const api = useApi();

  const [status, setStatus] = createSignal<NetworkStatus | null>(null);
  const [loading, setLoading] = createSignal(true);
  const [mode, setMode] = createSignal<"dhcp" | "static">("dhcp");
  const [ip, setIp] = createSignal("");
  const [prefix, setPrefix] = createSignal(24);
  const [gateway, setGateway] = createSignal("");
  const [dns, setDns] = createSignal("");
  const [resultMsg, setResultMsg] = createSignal<string | null>(null);
  const [error, setError] = createSignal<string | null>(null);
  const [applying, setApplying] = createSignal(false);

  onMount(async () => {
    const s = await api.getNetwork();
    if (s) {
      setStatus(s);
      setMode(s.mode);
      setIp(s.ip_address ?? "");
      setPrefix(s.prefix ?? 24);
      setGateway(s.gateway ?? "");
      setDns(s.dns ?? "");
    }
    setLoading(false);
  });

  function validateStatic(): string | null {
    if (!IP_RE.test(ip())) return "IP no valida";
    const p = prefix();
    if (p < 1 || p > 32) return "Mascara (prefijo) debe estar entre 1 y 32";
    if (!IP_RE.test(gateway())) return "Puerta de enlace no valida";
    if (dns() && !IP_RE.test(dns())) return "DNS no valido";
    return null;
  }

  async function apply() {
    setApplying(true);
    setResultMsg(null);
    setError(null);

    let message: string | null = null;
    if (mode() === "dhcp") {
      const r = await api.applyDhcp();
      message = r?.message ?? "Error al aplicar DHCP";
      if (r && !r.success) setError(message);
    } else {
      const err = validateStatic();
      if (err) {
        setError(err);
        setApplying(false);
        return;
      }
      const r = await api.applyStatic(ip(), prefix(), gateway(), dns() || null);
      message = r?.message ?? "Error al aplicar IP estatica";
      if (r && !r.success) setError(message);
    }

    setResultMsg(message);
    setApplying(false);
  }

  return (
    <div class="min-h-screen flex flex-col items-center justify-center bg-[#141428] p-6">
      <div class="bg-[#0f0f23] border border-[#2a2a5e] rounded-2xl p-8 w-[420px] max-w-[94vw] shadow-2xl">
        <h2 class="text-xl font-bold text-gray-200 mb-6 text-center tracking-wider">
          CONFIGURAR IP
        </h2>

        <Show when={loading()}>
          <div class="text-gray-500 text-center py-8">Cargando red...</div>
        </Show>

        <Show when={!loading()}>
          {/* Estado actual */}
          <div class="bg-[#1a1a3e] rounded-lg p-4 mb-6 text-sm space-y-1">
            <div class="flex justify-between">
              <span class="text-gray-500">Interfaz</span>
              <span class="text-gray-300 font-mono">{status()?.interface ?? "-"}</span>
            </div>
            <div class="flex justify-between">
              <span class="text-gray-500">IP actual</span>
              <span class="text-gray-300 font-mono">{status()?.ip_address ?? "-"}</span>
            </div>
            <div class="flex justify-between">
              <span class="text-gray-500">Modo</span>
              <span class="text-[#4a9eff] font-semibold uppercase">
                {status()?.mode === "static" ? "Estatica" : "DHCP"}
              </span>
            </div>
          </div>

          {/* Selector de modo */}
          <div class="grid grid-cols-2 gap-3 mb-6">
            <button
              onClick={() => setMode("dhcp")}
              class="py-3 rounded-xl border text-sm font-bold transition-all"
              classList={{
                "bg-[#0f3460] border-[#4a9eff] text-white": mode() === "dhcp",
                "bg-[#1a1a3e] border-[#2a2a5e] text-gray-400": mode() !== "dhcp",
              }}
            >
              DHCP (auto)
            </button>
            <button
              onClick={() => setMode("static")}
              class="py-3 rounded-xl border text-sm font-bold transition-all"
              classList={{
                "bg-[#0f3460] border-[#4a9eff] text-white": mode() === "static",
                "bg-[#1a1a3e] border-[#2a2a5e] text-gray-400": mode() !== "static",
              }}
            >
              IP estatica
            </button>
          </div>

          {/* Formulario estatico */}
          <Show when={mode() === "static"}>
            <div class="space-y-3 mb-6">
              <Field label="Direccion IP" value={ip()} onChange={setIp} placeholder="192.168.1.50" />
              <Field
                label="Prefijo (mascara)"
                value={String(prefix())}
                onChange={(v) => setPrefix(parseInt(v || "24", 10))}
                placeholder="24"
                inputmode="numeric"
              />
              <Field label="Puerta de enlace" value={gateway()} onChange={setGateway} placeholder="192.168.1.1" />
              <Field label="DNS (opcional)" value={dns()} onChange={setDns} placeholder="192.168.1.1" />
            </div>
          </Show>

          <Show when={error()}>
            <div class="bg-red-900/40 border border-red-600/50 text-red-300 text-sm rounded-lg px-4 py-2 mb-4">
              {error()}
            </div>
          </Show>

          <Show when={resultMsg()}>
            <div class="bg-yellow-900/40 border border-yellow-600/50 text-yellow-200 text-sm rounded-lg px-4 py-2 mb-4">
              {resultMsg()}
              <div class="text-yellow-400/80 text-xs mt-1">
                La conexion se cortara momentaneamente. Recarga la web con la nueva IP.
              </div>
            </div>
          </Show>

          <button
            onClick={apply}
            disabled={applying()}
            class="w-full py-3 rounded-xl bg-[#e94560] hover:bg-[#f05a74] active:bg-[#c23952]
                   text-white font-bold text-sm transition-colors
                   disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
          >
            {applying() ? "Aplicando..." : "Aplicar"}
          </button>

          <button
            onClick={props.onBack}
            class="w-full mt-3 py-3 rounded-xl bg-[#141428] hover:bg-[#1e1e3a]
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
  inputmode?: string;
}) {
  return (
    <label class="block">
      <span class="text-gray-500 text-xs mb-1 block">{props.label}</span>
      <input
        value={props.value}
        onInput={(e) => props.onChange(e.currentTarget.value)}
        placeholder={props.placeholder}
        inputmode={props.inputmode as "text" | "numeric" | undefined}
        class="w-full bg-[#1a1a3e] border border-[#2a2a5e] rounded-lg px-3 py-2
               text-gray-200 font-mono text-sm focus:outline-none focus:border-[#4a9eff]"
      />
    </label>
  );
}
