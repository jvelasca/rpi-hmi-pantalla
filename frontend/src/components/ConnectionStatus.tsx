/**
 * ConnectionStatus — Indicador de estado de conexion al backend.
 */

interface ConnectionStatusProps {
  connected: boolean;
  error: string | null;
}

export function ConnectionStatus(props: ConnectionStatusProps) {
  return (
    <footer class="bg-black border-t border-[#1a1a3e] px-4 py-1.5 flex items-center justify-between text-xs text-gray-600">
      <span>{new Date().toLocaleTimeString()}</span>
      <div class="flex items-center gap-3">
        {props.error && (
          <span class="text-red-500 truncate max-w-[200px]" title={props.error}>
            {props.error}
          </span>
        )}
        <span
          classList={{
            "text-green-600": props.connected,
            "text-red-600": !props.connected,
          }}
        >
          {props.connected ? "API OK" : "API --"}
        </span>
      </div>
    </footer>
  );
}
