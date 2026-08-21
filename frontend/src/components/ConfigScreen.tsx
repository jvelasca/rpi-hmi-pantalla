/**
 * ConfigScreen — Modal de configuracion con opciones de diagnostico.
 * Muestra los accesos a: Prueba de Pantalla, Calibracion Tactil,
 * Configurar IP, Texto y Fuente, Contrasena y Volver.
 */

interface ConfigScreenProps {
  onScreenTest: () => void;
  onTouchCalibration: () => void;
  onNetwork: () => void;
  onFont: () => void;
  onSecurity: () => void;
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

          {/* Configurar IP */}
          <button
            onClick={props.onNetwork}
            class="flex items-center gap-4 px-6 py-4 rounded-xl
                   bg-[#1a1a3e] hover:bg-[#2a2a5e] active:bg-[#e94560]/20
                   border border-[#2a2a5e] hover:border-[#e94560]/50
                   transition-all duration-200
                   focus:outline-none focus:ring-2 focus:ring-[#e94560]/50
                   group"
          >
            {/* Icono red */}
            <svg
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="1.5"
              stroke-linecap="round"
              stroke-linejoin="round"
              class="w-7 h-7 text-[#ffb84a] group-hover:text-[#ffcc80] transition-colors shrink-0"
            >
              <rect x="9" y="2" width="6" height="6" rx="1" />
              <rect x="2" y="16" width="6" height="6" rx="1" />
              <rect x="16" y="16" width="6" height="6" rx="1" />
              <path d="M12 8v4M5 16v-4a7 7 0 0 1 14 0v4" />
            </svg>
            <div class="text-left">
              <div class="text-gray-200 text-sm font-semibold group-hover:text-white transition-colors">
                Configurar IP
              </div>
              <div class="text-gray-500 text-xs mt-0.5">
                Cambiar IP estatica o DHCP
              </div>
            </div>
          </button>

          {/* Texto y Fuente */}
          <button
            onClick={props.onFont}
            class="flex items-center gap-4 px-6 py-4 rounded-xl
                   bg-[#1a1a3e] hover:bg-[#2a2a5e] active:bg-[#e94560]/20
                   border border-[#2a2a5e] hover:border-[#e94560]/50
                   transition-all duration-200
                   focus:outline-none focus:ring-2 focus:ring-[#e94560]/50
                   group"
          >
            {/* Icono fuente */}
            <svg
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="1.5"
              stroke-linecap="round"
              stroke-linejoin="round"
              class="w-7 h-7 text-[#be82ff] group-hover:text-[#d3a4ff] transition-colors shrink-0"
            >
              <polyline points="4 7 4 4 20 4 20 7" />
              <line x1="12" y1="4" x2="12" y2="20" />
              <polyline points="9 20 12 17 15 20" />
            </svg>
            <div class="text-left">
              <div class="text-gray-200 text-sm font-semibold group-hover:text-white transition-colors">
                Texto y Fuente
              </div>
              <div class="text-gray-500 text-xs mt-0.5">
                Elegir fuente y tamano de texto
              </div>
            </div>
          </button>

          {/* Contrasena */}
          <button
            onClick={props.onSecurity}
            class="flex items-center gap-4 px-6 py-4 rounded-xl
                   bg-[#1a1a3e] hover:bg-[#2a2a5e] active:bg-[#e94560]/20
                   border border-[#2a2a5e] hover:border-[#e94560]/50
                   transition-all duration-200
                   focus:outline-none focus:ring-2 focus:ring-[#e94560]/50
                   group"
          >
            {/* Icono candado */}
            <svg
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="1.5"
              stroke-linecap="round"
              stroke-linejoin="round"
              class="w-7 h-7 text-[#ff6b8a] group-hover:text-[#ff8fa6] transition-colors shrink-0"
            >
              <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
              <path d="M7 11V7a5 5 0 0 1 10 0v4" />
            </svg>
            <div class="text-left">
              <div class="text-gray-200 text-sm font-semibold group-hover:text-white transition-colors">
                Contrasena
              </div>
              <div class="text-gray-500 text-xs mt-0.5">
                Activar, desactivar o cambiar la clave
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
