/**
 * ScreenTest — Prueba visual de pantalla.
 * Cicla por patrones de prueba: barras de color, grilla, degradados,
 * colores solidos (R, G, B, W, K) para verificar el display.
 *
 * Disenado para pantalla 480x320 (ILI9486).
 */

import { createSignal, For } from "solid-js";

interface ScreenTestProps {
  onBack: () => void;
}

const PATTERNS = [
  "Barras de Color",
  "Rojo",
  "Verde",
  "Azul",
  "Blanco",
  "Negro",
  "Grilla",
  "Degradado",
] as const;

export function ScreenTest(props: ScreenTestProps) {
  const [pattern, setPattern] = createSignal<number>(0);

  function nextPattern() {
    setPattern((p) => (p + 1) % PATTERNS.length);
  }

  function prevPattern() {
    setPattern((p) => (p - 1 + PATTERNS.length) % PATTERNS.length);
  }

  const currentIndex = pattern();
  const currentName = PATTERNS[currentIndex];

  return (
    <div class="fixed inset-0 z-50 flex flex-col bg-black">
      {/* Contenido del test */}
      <div class="flex-1 relative overflow-hidden">
        {currentIndex === 0 && <ColorBars />}
        {currentIndex === 1 && <SolidColor color="#ff0000" />}
        {currentIndex === 2 && <SolidColor color="#00ff00" />}
        {currentIndex === 3 && <SolidColor color="#0000ff" />}
        {currentIndex === 4 && <SolidColor color="#ffffff" />}
        {currentIndex === 5 && <SolidColor color="#000000" />}
        {currentIndex === 6 && <GridPattern />}
        {currentIndex === 7 && <GradientPattern />}
      </div>

      {/* Barra de navegacion inferior */}
      <div class="bg-[#0f0f23]/90 backdrop-blur-sm border-t border-[#1a1a3e] px-4 py-3 flex items-center justify-between">
        {/* Flecha izquierda */}
        <button
          onClick={prevPattern}
          class="w-10 h-10 rounded-lg bg-[#1a1a3e] hover:bg-[#2a2a5e]
                 border border-[#2a2a5e] flex items-center justify-center
                 transition-colors focus:outline-none focus:ring-2 focus:ring-[#e94560]/50"
          title="Patron anterior"
        >
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none"
               stroke="currentColor" stroke-width="2" stroke-linecap="round"
               stroke-linejoin="round" class="w-5 h-5 text-gray-300">
            <polyline points="15 18 9 12 15 6" />
          </svg>
        </button>

        {/* Nombre del patron + indicador */}
        <div class="flex flex-col items-center gap-1">
          <span class="text-sm font-semibold text-gray-200 tracking-wider">
            {currentName}
          </span>
          <span class="text-xs text-gray-500">
            {currentIndex + 1} / {PATTERNS.length}
          </span>
        </div>

        {/* Flecha derecha */}
        <button
          onClick={nextPattern}
          class="w-10 h-10 rounded-lg bg-[#1a1a3e] hover:bg-[#2a2a5e]
                 border border-[#2a2a5e] flex items-center justify-center
                 transition-colors focus:outline-none focus:ring-2 focus:ring-[#e94560]/50"
          title="Siguiente patron"
        >
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none"
               stroke="currentColor" stroke-width="2" stroke-linecap="round"
               stroke-linejoin="round" class="w-5 h-5 text-gray-300">
            <polyline points="9 18 15 12 9 6" />
          </svg>
        </button>
      </div>

      {/* Boton Volver */}
      <div class="bg-[#0f0f23]/90 backdrop-blur-sm border-t border-[#1a1a3e] px-4 py-2 flex justify-center">
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

// ── Subcomponentes de patrones ──────────────────────────────

/** Barras horizontales de color (RGB + CMY + W + K) */
function ColorBars() {
  const bars = [
    { color: "#ff0000", label: "R" },
    { color: "#ff8800", label: "O" },
    { color: "#ffff00", label: "Y" },
    { color: "#00ff00", label: "G" },
    { color: "#00ffff", label: "C" },
    { color: "#0088ff", label: "B" },
    { color: "#ffffff", label: "W" },
    { color: "#000000", label: "K" },
  ];

  return (
    <div class="w-full h-full flex flex-col">
      <For each={bars}>
        {(bar) => (
          <div
            class="flex-1 flex items-center justify-center"
            style={{ background: bar.color }}
          >
            <span
              class="text-xl font-bold drop-shadow-lg"
              style={{
                color: bar.color === "#000000" ? "#ffffff" : "#000000",
              }}
            >
              {bar.label}
            </span>
          </div>
        )}
      </For>
    </div>
  );
}

/** Color solido */
function SolidColor(props: { color: string }) {
  return (
    <div class="w-full h-full" style={{ background: props.color }}>
      <div class="absolute top-4 left-4 text-xs font-mono opacity-40"
           style={{ color: props.color === "#000000" ? "#ffffff" : "#000000" }}>
        {props.color}
      </div>
    </div>
  );
}

/** Grilla de lineas finas para verificar pixeles */
function GridPattern() {
  return (
    <div class="w-full h-full bg-gray-900 relative overflow-hidden">
      {/* Lineas verticales */}
      <svg class="absolute inset-0 w-full h-full" xmlns="http://www.w3.org/2000/svg">
        <defs>
          <pattern id="grid" width="40" height="40" patternUnits="userSpaceOnUse">
            <rect width="40" height="40" fill="none" />
            <path d="M 40 0 L 0 0 0 40" fill="none" stroke="#ffffff" stroke-width="0.5" opacity="0.2" />
          </pattern>
          <pattern id="gridFine" width="10" height="10" patternUnits="userSpaceOnUse">
            <rect width="10" height="10" fill="none" />
            <path d="M 10 0 L 0 0 0 10" fill="none" stroke="#ffffff" stroke-width="0.3" opacity="0.08" />
          </pattern>
        </defs>
        <rect width="100%" height="100%" fill="url(#gridFine)" />
        <rect width="100%" height="100%" fill="url(#grid)" />
      </svg>

      {/* Cruz central */}
      <div class="absolute inset-0 flex items-center justify-center">
        <div class="relative w-4 h-4">
          <div class="absolute top-1/2 left-0 right-0 h-px bg-red-500/50" />
          <div class="absolute left-1/2 top-0 bottom-0 w-px bg-red-500/50" />
        </div>
      </div>

      {/* Esquinas con marcas en L */}
      <div class="absolute top-0 left-0 w-8 h-8 border-t-2 border-l-2 border-white/15" />
      <div class="absolute top-0 right-0 w-8 h-8 border-t-2 border-r-2 border-white/15" />
      <div class="absolute bottom-0 left-0 w-8 h-8 border-b-2 border-l-2 border-white/15" />
      <div class="absolute bottom-0 right-0 w-8 h-8 border-b-2 border-r-2 border-white/15" />
    </div>
  );
}

/** Degradado horizontal + vertical combinado */
function GradientPattern() {
  return (
    <div class="w-full h-full relative">
      {/* Degradado horizontal (izq negro -> der blanco) */}
      <div
        class="absolute inset-0"
        style={{
          background: "linear-gradient(to right, #000000, #ffffff)",
        }}
      />
      {/* Degradado vertical (arriba transparente -> abajo rojo) */}
      <div
        class="absolute inset-0"
        style={{
          background: "linear-gradient(to bottom, transparent, rgba(255,0,0,0.6))",
        }}
      />
      {/* Etiquetas */}
      <div class="absolute top-2 left-2 text-[10px] font-mono text-white/30">0,0</div>
      <div class="absolute top-2 right-2 text-[10px] font-mono text-black/30">479,0</div>
      <div class="absolute bottom-2 left-2 text-[10px] font-mono text-white/30">0,319</div>
      <div class="absolute bottom-2 right-2 text-[10px] font-mono text-black/30">479,319</div>
    </div>
  );
}
