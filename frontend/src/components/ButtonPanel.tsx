/**
 * ButtonPanel — Boton virtual con contador de pulsaciones.
 */

import type { ButtonState } from "@/types/api";

interface ButtonPanelProps {
  button: ButtonState;
  onPress: () => void;
  disabled?: boolean;
}

export function ButtonPanel(props: ButtonPanelProps) {
  const { button, onPress, disabled } = props;

  return (
    <div class="bg-[#1e1e3c] rounded-lg border border-[#323264] p-5 flex flex-col items-center gap-4 min-w-[200px]">
      <h2 class="text-[#a0a0b4] text-sm font-medium">BOTON</h2>

      {/* Boton circular */}
      <button
        onClick={onPress}
        disabled={disabled}
        class="w-28 h-28 rounded-full flex items-center justify-center
               text-white font-bold text-sm transition-all duration-150
               disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer select-none
               shadow-lg"
        classList={{
          "bg-[#0f3460] hover:bg-[#194b8c] active:bg-[#081e3c] active:scale-95":
            !button.pressed,
          "bg-green-700 scale-95": button.pressed,
        }}
      >
        <span
          classList={{
            "text-white": !button.pressed,
            "text-green-200": button.pressed,
          }}
        >
          {button.pressed ? "PULSADO" : "PULSAR"}
        </span>
      </button>

      {/* Contador */}
      <div class="text-center">
        <span class="text-[#a0a0b4] text-xs">Pulsaciones</span>
        <div class="text-3xl font-bold text-[#e94560] mt-1 tabular-nums">
          {button.press_count}
        </div>
      </div>
    </div>
  );
}
