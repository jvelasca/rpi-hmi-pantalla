# Plan de Refactorización Orquestada con Subagentes

> Fuente de verdad de la ejecución del refactor. La mantiene **solo el hilo principal**.
> Los subagentes NO editan este archivo; escriben sus propios *handoffs*.

## 1. Objetivo

Corregir los hallazgos consolidados (auditoría interna + externa) sin que:
- el hilo principal pierda la visión global de los cambios, y
- ningún subagente pierda contexto al saturarse.

## 2. Principios de orquestación

1. **Visión global única** → `docs/audits/refactor/ESTADO.md` (lo mantiene el hilo principal).
2. **Handoff obligatorio** → cada subagente escribe `docs/audits/refactor/handoffs/<ws-id>.md` antes de terminar.
3. **Saturación vigilada** → si un subagente detecta que se queda sin contexto, escribe un checkpoint parcial y se detiene; el hilo principal relanza un agente *resume* con ese handoff como entrada.
4. **Cero colisiones** → cada archivo del repo pertenece a **un único** workstream (mapa de propiedad §6).
5. **Unidad verificable** → el hilo principal hace commit por workstream terminado y verificado. El historial git es la memoria inmutable.

## 3. Archivos de estado

| Archivo | Responsable | Contenido |
|---|---|---|
| `docs/audits/refactor/ESTADO.md` | Hilo principal | Fase actual, estado por workstream, decisiones, punteros a handoffs |
| `docs/audits/refactor/handoffs/<ws-id>.md` | Subagente | Resultado + archivos + verificación + decisiones + texto de paso |

## 4. Protocolo de handoff (plantilla obligatoria)

Todo subagente escribe, al finalizar (o al saturarse), un archivo con esta estructura exacta:

```markdown
# Handoff <WS-ID> — <Nombre>
## Resultado
## Archivos modificados (lista con rutas)
## Verificación ejecutada (comandos + resultado)
## Decisiones tomadas (y por qué)
## Riesgos / pendientes
## Texto de paso al siguiente agente
```

**Regla crítica:** si el subagente se satura, escribe el handoff con el estado *parcial* y un `## Texto de paso` que diga exactamente desde dónde continuar. Nunca devolver "he terminado" sin handoff.

## 5. Protocolo de saturación

- El subagente hace **checkpoints incrementales**: ante trabajo largo, escribe el handoff a mitad de tarea.
- Si detecta que se acerca al límite de contexto, **detiene la tarea, escribe handoff y devuelve** un resumen corto.
- El hilo principal **relanza** un subagente con el handoff como contexto (`resume`), nunca reinicia desde cero.

## 6. Mapa de propiedad de archivos (anti-colisión)

| Workstream | Archivos que posee en exclusiva |
|---|---|
| A1 — Display tests + feedback botón | `display/tests/**`, `display/app.py` |
| A2 — mypy verde | `backend/pyproject.toml`, `backend/app/**` (solo anotaciones) |
| B — Seguridad red + README + sudoers | `backend/app/api/network.py`, `backend/app/api/deps.py` (nuevo), `backend/app/config.py`, `backend/app/main.py`, `README.md` (GPIO17 + red), `config/sudoers.d/rpi-hmi` (nuevo) |
| C — Display DRM hardening | `display/ui/screen.py`, `config/systemd/rpi-hmi-display.service` |
| D — Frontend hardening | `frontend/src/**`, `frontend/vite.config.ts`, `frontend/package.json` |
| E — Arquitectura | `backend/app/services/state_manager.py`, `backend/app/services/persistence.py`, `backend/app/services/network_service.py`, `config/systemd/rpi-hmi-backend.service` |
| F — Docs/consistencia | `docs/**`, `VERSION`, `README.md` (conteo de tests), cadenas de versión en `display/app.py` |

> `display/app.py` aparece en A1 y F: **F se ejecuta después de A1** (no en paralelo).
> `README.md` aparece en B y F: **F se ejecuta después de B** (no en paralelo).

## 7. Fases y orden de ejecución

### Fase 0 — Setup (hilo principal, sin subagentes)
1. `git status` limpio + commit base del estado actual (punto de restauración).
2. Crear `docs/audits/refactor/ESTADO.md` y `docs/audits/refactor/handoffs/`.
3. Fijar baseline: `pytest` (16 fail), `mypy` (57 err), `vitest` (16 pass).

### Fase 1 — Puerta de calidad (PARALELO: A1 ∥ A2)
- **A1**: corregir 15 tests de display con `__new__` + implementar feedback no-bloqueante del botón. Done: `pytest display/tests/` verde.
- **A2**: `plugins=["pydantic.mypy"]` + violaciones strict reales (`Task[Any]`, `Queue[Any]`, `Literal`, stubs `yaml`). Done: `mypy app/ --strict` = 0 errores.
- **Gate**: el hilo principal ejecuta `pytest backend/tests/ display/tests/` + `mypy` + `vitest`. Si todo verde → commit y se abre Fase 2.

### Fase 2 — Seguridad y hardening (PARALELO: B ∥ C ∥ D)
- **B**: proteger `/api/network/*` (mover a `/admin/network/*` o `SECURITY_MODE=local|protected`), corregir README GPIO17, documentar/crear sudoers `pi → /usr/bin/nmcli`.
- **C**: eliminar fallback automático DRM→mock en producción (`screen.py` → `exit 1` + reinicio systemd); detección DRM real (connector status).
- **D**: validación runtime WS con Zod, máquina de estados `NORMAL→RESYNCING`, quitar IP fija de `vite.config.ts`.
- **Gate**: `pytest` + `mypy` + `vitest` + `npm run build` verdes. Commit por workstream.

### Fase 3 — Arquitectura (SECUENCIAL: E, con resume si satura)
- **E**: dividir `StateManager` (DeviceState/EventBus/Persistence/WebSocketHub), sacar `subprocess` de `network_service` del event loop (`asyncio.to_thread`), schema versionado + migraciones SQLite, watchdog + límites systemd.
- **Gate**: suite completa verde + smoke de importación del backend.

### Fase 4 — Docs/consistencia (SECUENCIAL: F)
- **F**: `docs/SECURITY.md` (modelo de amenazas PUBLIC/LOCAL/ADMIN), unificar versiones visibles, limpiar conteo de tests del README, documentar safe-state.

### Fase 5 — Verificación final (hilo principal)
1. CI equivalente completo (pytest + ruff + mypy + vitest + build).
2. Revisar todos los handoffs y cerrar pendientes.
3. Actualizar `ESTADO.md` a `COMPLETADO` y commit final.

## 8. Tipo de subagente

- Workstreams de código (A1, A2, B, C, D, E, F): subagente `generalPurpose` (local, edita código y ejecuta comandos).
- Verificaciones de comandos puras (gates): el hilo principal, con `shell`.

## 9. Reglas de no-pérdida (resumen)

1. Ningún subagente toca archivos fuera de su mapa de propiedad.
2. Ningún subagente termina sin handoff en `docs/audits/refactor/handoffs/`.
3. El hilo principal actualiza `ESTADO.md` tras cada subagente y tras cada gate.
4. Cada commit es un workstream verificado (revertible e inspeccionable).
5. Si un subagente se satura → checkpoint parcial + resume con handoff, jamás reinicio desde cero.
