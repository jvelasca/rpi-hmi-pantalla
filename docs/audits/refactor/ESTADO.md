# Estado Global de la Refactorización

> **ÚNICO editor de este archivo: el hilo principal.**
> Los subagentes escriben en `handoffs/<ws-id>.md` y devuelven su resumen; jamás editan aquí.

## Estado general

- **Fase actual:** 0 — Setup
- **Última actualización:** 2026-08-20
- **Baseline puerta de calidad:** pytest = 16 FAIL / 261 PASS · mypy = 57 errores · vitest = 16 PASS

## Workstreams

| ID | Nombre | Fase | Estado | Handoff | Commit |
|---|---|---|---|---|---|
| A1 | Display tests + feedback botón | 1 | ⏳ pendiente | — | — |
| A2 | mypy verde | 1 | ⏳ pendiente | — | — |
| B | Seguridad red + README + sudoers | 2 | ⏳ pendiente | — | — |
| C | Display DRM hardening | 2 | ⏳ pendiente | — | — |
| D | Frontend hardening | 2 | ⏳ pendiente | — | — |
| E | Arquitectura (StateManager/persistencia/red/watchdog) | 3 | ⏳ pendiente | — | — |
| F | Docs/consistencia | 4 | ⏳ pendiente | — | — |

Leyenda de estado: ⏳ pendiente · 🟡 en curso · ✅ completado · ⛔ bloqueado

## Decisiones registradas

| # | Decisión | Workstream | Fecha |
|---|---|---|---|
| 1 | La puerta de calidad va primero (Fase 1); es prerrequisito de todo lo demás | Global | 2026-08-20 |
| 2 | Modelo de seguridad: `SECURITY_MODE=local\|protected` (configurable), no hardcodear | B | 2026-08-20 |
| 3 | `display/app.py` se reparte A1→F en secuencia (nunca paralelo) | A1, F | 2026-08-20 |
| 4 | `README.md` se reparte B→F en secuencia (nunca paralelo) | B, F | 2026-08-20 |

## Goles (gates)

| Gate | Criterio | Estado |
|---|---|---|
| G1 (post Fase 1) | `pytest backend/tests/ display/tests/` verde · `mypy app/ --strict` = 0 · `vitest` verde | ⏳ |
| G2 (post Fase 2) | G1 + `npm run build` verde | ⏳ |
| G3 (post Fase 3) | G2 + smoke de importación backend | ⏳ |
| G4 (final) | CI equivalente completo (pytest + ruff + mypy + vitest + build) | ⏳ |

## Log de ejecución

- 2026-08-20 — Fase 0 iniciada. Baseline registrado. Infraestructura de orquestación creada.
