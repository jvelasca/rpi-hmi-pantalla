/**
 * LedPanel — Panel de control del LED con indicador visual e interruptor.
 */

import type { LedState } from "@/types/api";

interface LedPanelProps {
  led: LedState;
  onToggle: () => void;
  disabled?: boolean;
}

export function LedPanel(props: LedPanelProps) {
  return (
    <div class="bg-[#1e1e3c] rounded-lg border border-[#323264] p-5 flex flex-col items-center gap-4 min-w-[200px]">
      <h2 class="text-[#a0a0b4] text-sm font-medium">INTERRUPTOR ON/OFF</h2>

      {/* LED 1 (rojo) */}
      <div
        class="relative w-24 h-24 rounded-full flex items-center justify-center transition-all duration-200"
        classList={{
          "shadow-[0_0_30px_rgba(255,0,0,0.6)]": props.led.state,
          "shadow-none": !props.led.state,
        }}
      >
        {/* Glow layers */}
        {props.led.state && (
          <>
            <div class="absolute inset-[-6px] rounded-full bg-red-950/40" />
            <div class="absolute inset-[-2px] rounded-full bg-red-700/60" />
          </>
        )}
        <div
          class="absolute inset-0 rounded-full"
          classList={{
            "bg-red-600": props.led.state,
            "bg-gray-700": !props.led.state,
          }}
        />
        <div
          class="absolute inset-[6px] rounded-full"
          classList={{
            "bg-red-500": props.led.state,
            "bg-gray-600": !props.led.state,
          }}
        />
        {/* Specular highlight */}
        <div
          class="absolute w-5 h-5 rounded-full"
          classList={{
            "bg-red-300 top-[14px] left-[14px]": props.led.state,
            "bg-gray-500 top-[14px] left-[14px]": !props.led.state,
          }}
        />
      </div>

      {/* Estado */}
      <span
        class="text-sm font-bold"
        classList={{
          "text-red-500": props.led.state,
          "text-gray-500": !props.led.state,
        }}
      >
        {props.led.label}
      </span>

      {/* Interruptor ON/OFF */}
      <button
        type="button"
        role="switch"
        aria-checked={props.led.state}
        aria-label="Interruptor ON/OFF"
        onClick={props.onToggle}
        disabled={props.disabled}
        class="w-full flex items-center justify-between gap-3 py-2.5 px-4 rounded text-sm font-bold
               transition-colors duration-150 select-none
               bg-[#0f3460] hover:bg-[#194b8c] active:bg-[#081e3c]
               text-white disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
      >
        <span
          class="text-xs font-bold tracking-widest"
          classList={{
            "text-white": props.led.state,
            "text-gray-400": !props.led.state,
          }}
        >
          {props.led.state ? "ON" : "OFF"}
        </span>
        <span
          class="relative inline-flex h-6 w-12 shrink-0 rounded-full transition-colors duration-200"
          classList={{
            "bg-emerald-500": props.led.state,
            "bg-[#323264]": !props.led.state,
          }}
        >
          <span
            class="absolute top-0.5 left-0.5 h-5 w-5 rounded-full bg-white shadow transition-transform duration-200"
            classList={{
              "translate-x-6": props.led.state,
              "translate-x-0": !props.led.state,
            }}
          />
        </span>
      </button>
    </div>
  );
}
