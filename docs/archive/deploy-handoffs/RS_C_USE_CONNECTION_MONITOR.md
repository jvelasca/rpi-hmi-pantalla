# Handoff RS_C — Extraer hook useConnectionMonitor

## Resultado
Completado (sin cambio de comportamiento). Se extrajo el polling REST de fallback
que estaba hardcodeado en `frontend/src/App.tsx` a un hook nuevo
`useConnectionMonitor`, manteniendo el intervalo exacto de 5000ms y el mismo
flujo: si el WebSocket esta conectado no poll, si no, consulta `getStatus()` y
aplica el resultado via `onStatus`.

## Que cambio
- **Antes**: `App.tsx` montaba un `setInterval` inline, hacia el polling y
  registraba `onCleanup(() => clearInterval(pollInterval))` directamente.
- **Despues**: `App.tsx` delega en `useConnectionMonitor({ isConnected, getStatus, onStatus })`.
  El hook encapsula el `setInterval(..., 5000)` y su `onCleanup`.
- Sin cambios de logica: mismo intervalo, misma guarda `if (isConnected()) return`,
  misma aplicacion de `led`/`button`.

## Archivos tocados (exclusiva)
- `frontend/src/hooks/useConnectionMonitor.ts` — [nuevo] hook con firma
  `useConnectionMonitor({ isConnected, getStatus, onStatus })`.
- `frontend/src/App.tsx` — [editado] sustituye el bloque de polling por la llamada
  al hook; se elimina `onCleanup` del import (ya no se usa) y se anade el import
  del hook.
- `frontend/src/tests/hooks.test.tsx` — [editado] anade `describe("useConnectionMonitor")`
  con 3 tests usando `vi.useFakeTimers()`.
- `docs/deploy/handoffs/RS_C_USE_CONNECTION_MONITOR.md` — [nuevo] este handoff.

## Verificacion ejecutada (salida real del gate)
Desde `frontend/`:

1. `npm run test` -> **verde** (19 passed).

```
 RUN  v4.1.10 E:/SINCRONIZADO/Informatica/Proyectos VisualStudio/Python/Rapsberry/Rpi_Pantalla_V1/frontend

 Test Files  2 passed (2)
      Tests  19 passed (19)
   Start at  17:05:32
   Duration  1.53s
```

2. `npm run build` -> **verde**.

```
vite v6.4.3 building for production...
transforming...
✓ 101 modules transformed.
rendering chunks...
computing gzip size...
dist/index.html                   0.53 kB │ gzip:  0.36 kB
dist/assets/index-C1KyBZzG.css   29.47 kB │ gzip:  6.23 kB
dist/assets/index-3ccw6mrw.js   121.43 kB │ gzip: 33.88 kB
✓ built in 733ms
```

## Tests anadidos (useConnectionMonitor)
- `isConnected() === true` -> NO llama a `getStatus` (avanza 10000ms y sigue sin llamadas).
- `isConnected() === false` -> llama a `getStatus` tras 5000ms y aplica `onStatus` con el resultado.
- Al hacer `dispose` (onCleanup via `createRoot`), el intervalo se limpia (no vuelve a llamar).

## Riesgos / pendientes
- Riesgo minimo: es un refactor 1:1. La unica diferencia observable es que el
  intervalo ahora se crea dentro del hook; el ciclo de vida (creacion/limpieza)
  sigue ligado al `createRoot`/owner de SolidJS de `App`, igual que antes.
- `onCleanup` se elimino del import de `App.tsx` porque quedo sin uso; verificar
  en futuros cambios que nadie lo requeria implicitamente (no se detecta uso restante).
- Los tests nuevos usan fake timers aislados (`beforeEach`/`afterEach` dentro del
  `describe`), por lo que no afectan a los tests de `useApi`/`useWebSocket`.

## Texto de paso al siguiente agente
Refactor completado y verificado: `npm run test` (19 passed) y `npm run build`
verdes. El polling de fallback queda en `useConnectionMonitor` sin cambio de
comportamiento. Sin deuda funcional pendiente en este ambito.
