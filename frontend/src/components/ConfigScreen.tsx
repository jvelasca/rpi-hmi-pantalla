/**
 * ConfigScreen — Modal de configuracion con opciones de diagnostico.
 * Muestra tres botones: Prueba de Pantalla, Calibracion Tactil, Volver.
 */

interface ConfigScreenProps {
  onScreenTest: () => void;
  onTouchCalibration: () => void;
  onBack: () => void;
}

export function ConfigScreen(props: ConfigScreenProps) {
  return (
    <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      {/* Modal */}
      <div class="bg-[#0f0f23] border border-[#2a2a5e] rounded-2xl p-8 w-[380px] max-w-[90vw] shadow-2xl shadow-black/50">
        {/* Titulo */}
        <h2 class="text-xl font-bold text-gray-200 mb-8 text-center tracking-wider">
          CONFIGURACION
        </h2>

        {/* Botones */}
        <div class="flex flex-col gap-4">
          {/* Prueba de Pantalla */}
          <button
            onClick={props.onScreenTest}
            class="flex items-center gap-4 px-6 py-4 rounded-xl
                   bg-[#1a1a3e] hover:bg-[#2a2a5e] active:bg-[#e94560]/20
                   border border-[#2a2a5e] hover:border-[#e94560]/50
                   transition-all duration-200
                   focus:outline-none focus:ring-2 focus:ring-[#e94560]/50
                   group"
          >
            {/* Icono monitor */}
            <svg
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="1.5"
              stroke-linecap="round"
              stroke-linejoin="round"
              class="w-7 h-7 text-[#4a9eff] group-hover:text-[#6ab4ff] transition-colors shrink-0"
            >
              <rect x="2" y="3" width="20" height="14" rx="2" ry="2" />
              <line x1="8" y1="21" x2="16" y2="21" />
              <line x1="12" y1="17" x2="12" y2="21" />
            </svg>
            <div class="text-left">
              <div class="text-gray-200 text-sm font-semibold group-hover:text-white transition-colors">
                Prueba de Pantalla
              </div>
              <div class="text-gray-500 text-xs mt-0.5">
                Patrones, colores y grilla
              </div>
            </div>
          </button>

          {/* Calibracion Tactil */}
          <button
            onClick={props.onTouchCalibration}
            class="flex items-center gap-4 px-6 py-4 rounded-xl
                   bg-[#1a1a3e] hover:bg-[#2a2a5e] active:bg-[#e94560]/20
                   border border-[#2a2a5e] hover:border-[#e94560]/50
                   transition-all duration-200
                   focus:outline-none focus:ring-2 focus:ring-[#e94560]/50
                   group"
          >
            {/* Icono touch */}
            <svg
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="1.5"
              stroke-linecap="round"
              stroke-linejoin="round"
              class="w-7 h-7 text-[#4aef9e] group-hover:text-[#6affb4] transition-colors shrink-0"
            >
              <path d="M12 2a4 4 0 0 1 4 4v4h2a2 2 0 0 1 2 2v7a4 4 0 0 1-4 4H8a4 4 0 0 1-4-4v-7a2 2 0 0 1 2-2h2V6a4 4 0 0 1 4-4z" />
              <line x1="12" y1="10" x2="12" y2="16" />
              <line x1="9" y1="13" x2="15" y2="13" />
            </svg>
            <div class="text-left">
              <div class="text-gray-200 text-sm font-semibold group-hover:text-white transition-colors">
                Calibracion Tactil
              </div>
              <div class="text-gray-500 text-xs mt-0.5">
                Verificar precision del touch
              </div>
            </div>
          </button>

          {/* Volver */}
          <button
            onClick={props.onBack}
            class="flex items-center gap-4 px-6 py-4 rounded-xl
                   bg-[#141428] hover:bg-[#1e1e3a]
                   border border-[#1a1a3e] hover:border-[#e94560]/30
                   transition-all duration-200
                   focus:outline-none focus:ring-2 focus:ring-[#e94560]/50
                   group mt-2"
          >
            {/* Icono flecha atras */}
            <svg
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="1.5"
              stroke-linecap="round"
              stroke-linejoin="round"
              class="w-7 h-7 text-gray-500 group-hover:text-[#e94560] transition-colors shrink-0"
            >
              <line x1="19" y1="12" x2="5" y2="12" />
              <polyline points="12 19 5 12 12 5" />
            </svg>
            <div class="text-left">
              <div class="text-gray-400 text-sm font-semibold group-hover:text-[#e94560] transition-colors">
                Volver
              </div>
              <div class="text-gray-600 text-xs mt-0.5">
                Regresar al panel principal
              </div>
            </div>
          </button>
        </div>
      </div>
    </div>
  );
}
