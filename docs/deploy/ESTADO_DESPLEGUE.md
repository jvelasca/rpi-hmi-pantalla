# Estado Global del Despliegue y Cierre de la FASE FINAL

> **ÚNICO editor de este archivo: el hilo principal.**
> Los subagentes escriben en `docs/deploy/handoffs/<ws-id>.md` y devuelven su resumen; jamás editan aquí.

## Estado general

- **Fase actual:** FASE FINAL — unificar auth, endurecer, desplegar y cerrar pendientes.
- **Última actualización:** 2026-08-20
- **Commit base (restauración):** `d16f991` (HEAD actual `1987ed9` = `d16f991` + docs/deploy/INICIO.md)
- **Baseline puerta de calidad:** pytest = 278 passed / 4 skipped · mypy = 0 errores (25 archivos) · ruff = 0 (0.16.3) · vitest = 16/16 · build OK

## Workstreams

| ID | Nombre | Prioridad | Estado | Handoff | Commit |
|---|---|---|---|---|---|
| H1 | Unificar auth REST+WS (seguridad) | P1 | ⏳ pendiente | `handoffs/H1.md` | — |
| H2 | Display + touch | P1/P2/P3 | ⏳ pendiente | `handoffs/H2.md` | — |
| H3 | Red + watchdog | P2/P3 | ⏳ pendiente | `handoffs/H3.md` | — |
| H4 | CI/CD + dependencias | P2 | ⏳ pendiente | `handoffs/H4.md` | — |
| H5 | Docs/versión | P2/P3 | ⏳ pendiente | `handoffs/H5.md` | — |
| H6 | Despliegue a la Pi (runbook) | P0 | ⏳ pendiente (requiere HW) | `handoffs/H6.md` | — |
| H7 | Arquitectura mayor (HMI vs Admin) | P3 | ⛔ bloqueado (decisión usuario) | — | — |
| H8 | Decisiones de producto | P3 | ⛔ bloqueado (decisión usuario) | — | — |

Leyenda de estado: ⏳ pendiente · 🟡 en curso · ✅ completado · ⛔ bloqueado

## Decisiones registradas

| # | Decisión | Workstream | Fecha |
|---|---|---|---|
| 1 | La puerta de calidad está verde (baseline) antes de tocar nada | Global | 2026-08-20 |
| 2 | Modelo de seguridad unificado: en `protected`, mutadores HMI (REST `POST /api/led|button|display/command` + `WS /ws`) exigen `X-API-Key`. `/admin/*` exige key **siempre** (independiente de `SECURITY_MODE`) | H1 | 2026-08-20 |
| 3 | Dos dependencias en `deps.py`: `require_admin_api_key` (respeta `SECURITY_MODE`) y `require_admin_api_key_always` (para `/admin/*`) | H1 | 2026-08-20 |
| 4 | `Screen.allow_mock_fallback` default → `False`; producción nunca cae a mock | H2 | 2026-08-20 |

## Gates

| Gate | Criterio | Estado |
|---|---|---|
| D1 (tras H1) | `pytest backend/tests/` + `mypy` + `ruff` verdes | ⏳ |
| D2 (tras H2+H3+H4+H5) | pytest (backend+display) + mypy + ruff + vitest + build verdes | ⏳ |
| D3 (tras H4) | checks nuevos de `ci.yml` reproducibles localmente | ⏳ |
| D4 (tras H6) | servicios vivos en la Pi + HIL + runbook | ⏳ (HW) |

## Log de ejecución

- 2026-08-20 — FASE FINAL iniciada. Baseline registrado (pytest 278/4/0 · mypy 0 · ruff 0 · vitest 16/16 · build OK).
- 2026-08-20 — `docs/deploy/INICIO.md` reescrito incorporando la 2ª auditoría externa (P0-P3, H1-H8, D1-D4).
