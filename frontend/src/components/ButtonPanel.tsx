/**
 * ButtonPanel — Pulsador con LED 2 (verde) y contador de pulsaciones.
 * Comportamiento momentaneo: el LED se enciende mientras se mantiene pulsado.
 */

import type { ButtonState } from "@/types/api";

interface ButtonPanelProps {
  button: ButtonState;
  onPress: () => void;
  onRelease: () => void;
  disabled?: boolean;
}

export function ButtonPanel(props: ButtonPanelProps) {
  return (
    <div class="bg-[#1e1e3c] rounded-lg border border-[#323264] p-5 flex flex-col items-center gap-4 min-w-[200px]">
      <h2 class="text-[#a0a0b4] text-sm font-medium">PULSADOR</h2>

      {/* LED 2 (verde) — refleja el estado del boton */}
      <div
        class="relative w-16 h-16 rounded-full flex items-center justify-center transition-all duration-150"
        classList={{
          "shadow-[0_0_24px_rgba(0,255,100,0.6)]": props.button.pressed,
          "shadow-none": !props.button.pressed,
        }}
      >
        <div
          class="absolute inset-0 rounded-full"
          classList={{
            "bg-green-500": props.button.pressed,
            "bg-gray-700": !props.button.pressed,
          }}
        />
        <div
          class="absolute inset-[4px] rounded-full"
          classList={{
            "bg-green-400": props.button.pressed,
            "bg-gray-600": !props.button.pressed,
          }}
        />
        <div
          class="absolute w-3 h-3 rounded-full top-[10px] left-[10px]"
          classList={{
            "bg-green-200": props.button.pressed,
            "bg-gray-500": !props.button.pressed,
          }}
        />
      </div>

      {/* Boton circular (momentaneo) */}
      <button
        onPointerDown={(e) => {
          e.preventDefault();
          props.onPress();
        }}
        onPointerUp={() => props.onRelease()}
        onPointerLeave={() => props.button.pressed && props.onRelease()}
        onPointerCancel={() => props.onRelease()}
        disabled={props.disabled}
        class="w-28 h-28 rounded-full flex items-center justify-center
               text-white font-bold text-sm transition-all duration-100
               disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer select-none
               shadow-lg touch-none"
        classList={{
          "bg-[#0f3460] hover:bg-[#194b8c] active:bg-[#081e3c]": !props.button.pressed,
          "bg-green-700 scale-95": props.button.pressed,
        }}
      >
        <span
          classList={{
            "text-white": !props.button.pressed,
            "text-green-200": props.button.pressed,
          }}
        >
          {props.button.pressed ? "PULSADO" : "PULSAR"}
        </span>
      </button>

      {/* Contador */}
      <div class="text-center">
        <span class="text-[#a0a0b4] text-xs">Pulsaciones</span>
        <div class="text-3xl font-bold text-[#e94560] mt-1 tabular-nums">
          {props.button.press_count}
        </div>
      </div>
    </div>
  );
}
