/**
 * TouchCalibration — Verificacion de precision tactil.
 * Muestra dianas en posiciones estrategicas (centro, 4 esquinas)
 * y registra donde toca realmente el usuario, mostrando la
 * diferencia entre la posicion esperada y la real.
 *
 * Soporta tanto touch (pointerdown) como mouse para pruebas en PC.
 */

import { createSignal, For, Show } from "solid-js";

interface TouchCalibrationProps {
  onBack: () => void;
}

interface TouchPoint {
  x: number; // X esperado (px)
  y: number; // Y esperado (px)
  label: string;
}

interface CalibrationResult {
  label: string;
  expectedX: number;
  expectedY: number;
  actualX: number | null;
  actualY: number | null;
  offsetX: number | null;
  offsetY: number | null;
}

const TARGETS: TouchPoint[] = [
  { x: 40, y: 40, label: "Sup-Izq" },
  { x: 440, y: 40, label: "Sup-Der" },
  { x: 240, y: 160, label: "Centro" },
  { x: 40, y: 280, label: "Inf-Izq" },
  { x: 440, y: 280, label: "Inf-Der" },
];

export function TouchCalibration(props: TouchCalibrationProps) {
  const [currentTarget, setCurrentTarget] = createSignal<number>(0);
  const [results, setResults] = createSignal<CalibrationResult[]>([]);
  const [phase, setPhase] = createSignal<"calibrating" | "results">("calibrating");
  const [lastTouch, setLastTouch] = createSignal<{ x: number; y: number } | null>(null);

  function handlePointerDown(e: PointerEvent) {
    if (phase() !== "calibrating") return;
    e.preventDefault();

    const rect = (e.currentTarget as HTMLElement).getBoundingClientRect();
    const actualX = Math.round(e.clientX - rect.left);
    const actualY = Math.round(e.clientY - rect.top);

    const idx = currentTarget();
    const target = TARGETS[idx];
    const newResult: CalibrationResult = {
      label: target.label,
      expectedX: target.x,
      expectedY: target.y,
      actualX,
      actualY,
      offsetX: actualX - target.x,
      offsetY: actualY - target.y,
    };

    setLastTouch({ x: actualX, y: actualY });
    setResults((prev) => [...prev, newResult]);

    if (idx + 1 < TARGETS.length) {
      setCurrentTarget(idx + 1);
      // Clear feedback after 400ms
      setTimeout(() => setLastTouch(null), 400);
    } else {
      setPhase("results");
    }
  }

  function reset() {
    setCurrentTarget(0);
    setResults([]);
    setPhase("calibrating");
    setLastTouch(null);
  }

  return (
    <div class="fixed inset-0 z-50 flex flex-col bg-[#0a0a1a]">
      <Show when={phase() === "calibrating"}>
        {/* Area de calibracion */}
        <div
          class="flex-1 relative overflow-hidden"
          onPointerDown={handlePointerDown}
        >
          {/* Dianas */}
          <For each={TARGETS}>
            {(target, i) => {
              const isCurrent = i() === currentTarget();
              const isDone = i() < currentTarget();
              return (
                <div
                  class="absolute transform -translate-x-1/2 -translate-y-1/2
                         flex flex-col items-center gap-1 pointer-events-none"
                  style={{
                    left: `${target.x}px`,
                    top: `${target.y}px`,
                  }}
                >
                  {/* Circulo diana */}
                  <div
                    class="rounded-full flex items-center justify-center transition-all duration-300"
                    classList={{
                      "w-12 h-12 border-2 border-[#4aef9e] bg-[#4aef9e]/10 animate-pulse":
                        isCurrent,
                      "w-10 h-10 border border-green-500/30 bg-green-500/5":
                        isDone,
                      "w-10 h-10 border border-white/10 bg-white/5": !isCurrent && !isDone,
                    }}
                  >
                    <div
                      class="rounded-full transition-all duration-300"
                      classList={{
                        "w-1.5 h-1.5 bg-[#4aef9e]": isCurrent,
                        "w-1 h-1 bg-green-500/50": isDone,
                        "w-1 h-1 bg-white/20": !isCurrent && !isDone,
                      }}
                    />
                  </div>

                  {/* Etiqueta */}
                  <span
                    class="text-xs font-mono transition-colors duration-300"
                    classList={{
                      "text-[#4aef9e]": isCurrent,
                      "text-green-500/50": isDone,
                      "text-white/20": !isCurrent && !isDone,
                    }}
                  >
                    {target.label}
                  </span>
                </div>
              );
            }}
          </For>

          {/* Feedback visual del ultimo toque (marca donde toco realmente) */}
          <Show when={lastTouch()}>
            {(touch) => (
              <div
                class="absolute w-8 h-8 rounded-full border-2 border-[#e94560]
                       bg-[#e94560]/20 animate-ping-once pointer-events-none
                       transform -translate-x-1/2 -translate-y-1/2"
                style={{
                  left: `${touch().x}px`,
                  top: `${touch().y}px`,
                }}
              />
            )}
          </Show>
        </div>

        {/* Instrucciones */}
        <div class="bg-[#0f0f23]/90 backdrop-blur-sm border-t border-[#1a1a3e] px-4 py-3">
          <p class="text-center text-sm text-gray-300">
            Toca la diana <span class="text-[#4aef9e] font-semibold">{TARGETS[currentTarget()].label}</span>
          </p>
          <p class="text-center text-xs text-gray-500 mt-1">
            {currentTarget() + 1} de {TARGETS.length}
          </p>
        </div>
      </Show>

      <Show when={phase() === "results"}>
        {/* Resultados */}
        <div class="flex-1 overflow-auto p-4">
          <h2 class="text-lg font-bold text-gray-200 mb-4 text-center">
            Resultados de Calibracion
          </h2>

          {/* Tabla de resultados */}
          <div class="overflow-x-auto">
            <table class="w-full text-xs font-mono">
              <thead>
                <tr class="border-b border-[#2a2a5e] text-gray-400">
                  <th class="text-left py-2 px-2">Posicion</th>
                  <th class="text-right py-2 px-2">Esperado</th>
                  <th class="text-right py-2 px-2">Real</th>
                  <th class="text-right py-2 px-2">Offset</th>
                </tr>
              </thead>
              <tbody>
                <For each={results()}>
                  {(r) => (
                    <tr class="border-b border-[#1a1a3e] text-gray-300">
                      <td class="py-2 px-2">{r.label}</td>
                      <td class="py-2 px-2 text-right">
                        ({r.expectedX},{r.expectedY})
                      </td>
                      <td class="py-2 px-2 text-right">
                        <Show when={r.actualX !== null} fallback={<span class="text-gray-600">--</span>}>
                          ({r.actualX},{r.actualY})
                        </Show>
                      </td>
                      <td
                        class="py-2 px-2 text-right"
                        classList={{
                          "text-green-400":
                            r.offsetX !== null &&
                            Math.abs(r.offsetX) <= 10 &&
                            r.offsetY !== null &&
                            Math.abs(r.offsetY) <= 10,
                          "text-yellow-400":
                            r.offsetX !== null &&
                            Math.abs(r.offsetX) <= 30 &&
                            r.offsetY !== null &&
                            Math.abs(r.offsetY) <= 30,
                          "text-red-400":
                            r.offsetX !== null &&
                            (Math.abs(r.offsetX) > 30 ||
                              (r.offsetY !== null && Math.abs(r.offsetY) > 30)),
                          "text-gray-600": r.offsetX === null,
                        }}
                      >
                        <Show
                          when={r.offsetX !== null}
                          fallback={<span>--</span>}
                        >
                          ({r.offsetX! > 0 ? "+" : ""}
                          {r.offsetX},{" "}
                          {r.offsetY! > 0 ? "+" : ""}
                          {r.offsetY})
                        </Show>
                      </td>
                    </tr>
                  )}
                </For>
              </tbody>
            </table>
          </div>

          {/* Leyenda */}
          <div class="flex gap-4 justify-center mt-4 text-xs">
            <span class="flex items-center gap-1 text-green-400">
              <span class="w-2 h-2 rounded-full bg-green-400" /> ≤10px
            </span>
            <span class="flex items-center gap-1 text-yellow-400">
              <span class="w-2 h-2 rounded-full bg-yellow-400" /> ≤30px
            </span>
            <span class="flex items-center gap-1 text-red-400">
              <span class="w-2 h-2 rounded-full bg-red-400" /> &gt;30px
            </span>
          </div>

          {/* Precisión global */}
          <div class="mt-4 p-3 rounded-lg bg-[#1a1a3e] border border-[#2a2a5e]">
            <p class="text-center text-sm text-gray-300">
              Precisión promedio:{" "}
              <span
                class="font-bold"
                classList={{
                  "text-green-400": avgOffset(results()) <= 15,
                  "text-yellow-400":
                    avgOffset(results()) > 15 && avgOffset(results()) <= 30,
                  "text-red-400": avgOffset(results()) > 30,
                }}
              >
                {avgOffset(results()).toFixed(1)}px
              </span>
            </p>
          </div>
        </div>
      </Show>

      {/* Botones inferiores */}
      <div class="bg-[#0f0f23]/90 backdrop-blur-sm border-t border-[#1a1a3e] px-4 py-3 flex justify-center gap-3">
        <Show when={phase() === "results"}>
          <button
            onClick={reset}
            class="flex items-center gap-2 px-4 py-2 rounded-lg
                   bg-[#1a1a3e] hover:bg-[#2a2a5e]
                   border border-[#4aef9e]/20 hover:border-[#4aef9e]/50
                   transition-colors focus:outline-none focus:ring-2 focus:ring-[#4aef9e]/50"
          >
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none"
                 stroke="currentColor" stroke-width="1.5" stroke-linecap="round"
                 stroke-linejoin="round" class="w-4 h-4 text-gray-400">
              <polyline points="1 4 1 10 7 10" />
              <path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10" />
            </svg>
            <span class="text-sm text-gray-400">Repetir</span>
          </button>
        </Show>

        <button
          onClick={props.onBack}
          class="flex items-center gap-2 px-6 py-2 rounded-lg
                 bg-[#1a1a3e] hover:bg-[#2a2a5e] active:bg-[#e94560]/20
                 border border-[#2a2a5e] hover:border-[#e94560]/50
                 transition-colors focus:outline-none focus:ring-2 focus:ring-[#e94560]/50"
        >
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none"
               stroke="currentColor" stroke-width="1.5" stroke-linecap="round"
               stroke-linejoin="round" class="w-5 h-5 text-gray-400">
            <line x1="19" y1="12" x2="5" y2="12" />
            <polyline points="12 19 5 12 12 5" />
          </svg>
          <span class="text-sm text-gray-400">Volver</span>
        </button>
      </div>
    </div>
  );
}

/** Calcula el offset promedio en pixeles */
function avgOffset(results: CalibrationResult[]): number {
  const valid = results.filter(
    (r) => r.offsetX !== null && r.offsetY !== null,
  );
  if (valid.length === 0) return 0;
  const sum = valid.reduce(
    (acc, r) =>
      acc + Math.sqrt((r.offsetX ?? 0) ** 2 + (r.offsetY ?? 0) ** 2),
    0,
  );
  return sum / valid.length;
}
