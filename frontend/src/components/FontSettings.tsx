/**
 * FontSettings — Seleccion de fuente y tamano de texto del display fisico.
 * Los cambios se aplican al instante en la pantalla de la Pi y se persisten.
 */

import { createSignal, onMount, Show } from "solid-js";
import type { DisplaySettings } from "@/types/api";
import { useApi } from "@/hooks/useApi";

interface FontSettingsProps {
  onBack: () => void;
}

const FONT_OPTIONS: { id: "dejavu" | "liberation"; label: string; desc: string }[] = [
  { id: "dejavu", label: "DejaVu Sans", desc: "Clasica y nitida" },
  { id: "liberation", label: "Liberation Sans", desc: "Compacta y legible" },
];

const SIZE_OPTIONS: { id: "small" | "medium" | "large"; label: string; desc: string }[] = [
  { id: "small", label: "Pequeno", desc: "Mas contenido" },
  { id: "medium", label: "Medio", desc: "Equilibrado" },
  { id: "large", label: "Grande", desc: "Maxima legibilidad" },
];

export function FontSettings(props: FontSettingsProps) {
  const api = useApi();

  const [loading, setLoading] = createSignal(true);
  const [fontFamily, setFontFamily] = createSignal<"dejavu" | "liberation">("dejavu");
  const [textSize, setTextSize] = createSignal<"small" | "medium" | "large">("medium");
  const [message, setMessage] = createSignal<string | null>(null);
  const [error, setError] = createSignal<string | null>(null);

  onMount(async () => {
    const s = await api.getDisplaySettings();
    if (s) {
      setFontFamily(s.font_family);
      setTextSize(s.text_size);
    }
    setLoading(false);
  });

  async function apply(family: string, size: string) {
    setMessage(null);
    setError(null);
    const r = await api.setDisplaySettings(family, size);
    if (r) {
      setFontFamily(r.font_family);
      setTextSize(r.text_size);
      setMessage("Ajustes aplicados en la pantalla de la Pi");
    } else {
      setError("No se pudieron aplicar los ajustes");
    }
  }

  return (
    <div class="min-h-screen flex flex-col items-center justify-center bg-[#141428] p-6">
      <div class="bg-[#0f0f23] border border-[#2a2a5e] rounded-2xl p-8 w-[420px] max-w-[94vw] shadow-2xl">
        <h2 class="text-xl font-bold text-gray-200 mb-6 text-center tracking-wider">
          TEXTO Y FUENTE
        </h2>

        <Show when={loading()}>
          <div class="text-gray-500 text-center py-8">Cargando ajustes...</div>
        </Show>

        <Show when={!loading()}>
          {/* Fuente */}
          <div class="text-gray-500 text-xs font-semibold mb-2 tracking-wider">FUENTE</div>
          <div class="grid grid-cols-2 gap-3 mb-6">
            {FONT_OPTIONS.map((opt) => (
              <button
                onClick={() => apply(opt.id, textSize())}
                class="rounded-xl border text-left px-4 py-3 transition-all"
                classList={{
                  "bg-[#0f3460] border-[#4a9eff]": fontFamily() === opt.id,
                  "bg-[#1a1a3e] border-[#2a2a5e] hover:border-[#4a9eff]/50":
                    fontFamily() !== opt.id,
                }}
              >
                <div
                  class="text-sm font-bold"
                  classList={{
                    "text-white": fontFamily() === opt.id,
                    "text-gray-300": fontFamily() !== opt.id,
                  }}
                >
                  {opt.label}
                </div>
                <div class="text-xs text-gray-500 mt-0.5">{opt.desc}</div>
              </button>
            ))}
          </div>

          {/* Tamano */}
          <div class="text-gray-500 text-xs font-semibold mb-2 tracking-wider">
            TAMANO DEL TEXTO
          </div>
          <div class="grid grid-cols-3 gap-3 mb-6">
            {SIZE_OPTIONS.map((opt) => (
              <button
                onClick={() => apply(fontFamily(), opt.id)}
                class="rounded-xl border px-2 py-3 transition-all text-center"
                classList={{
                  "bg-[#0f3460] border-[#4a9eff]": textSize() === opt.id,
                  "bg-[#1a1a3e] border-[#2a2a5e] hover:border-[#4a9eff]/50":
                    textSize() !== opt.id,
                }}
              >
                <div
                  class="text-sm font-bold"
                  classList={{
                    "text-white": textSize() === opt.id,
                    "text-gray-300": textSize() !== opt.id,
                  }}
                >
                  {opt.label}
                </div>
                <div class="text-[10px] text-gray-500 mt-0.5">{opt.desc}</div>
              </button>
            ))}
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

          <button
            onClick={props.onBack}
            class="w-full py-3 rounded-xl bg-[#141428] hover:bg-[#1e1e3a]
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
