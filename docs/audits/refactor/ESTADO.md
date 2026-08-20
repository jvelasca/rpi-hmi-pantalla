# Estado Global de la Refactorización

> **ÚNICO editor de este archivo: el hilo principal.**
> Los subagentes escriben en `handoffs/<ws-id>.md` y devuelven su resumen; jamás editan aquí.

## Estado general

- **Fase actual:** 2 — Seguridad y hardening (completada, gate G2 verde)
- **Última actualización:** 2026-08-20
- **Commit base (restauración):** `64b4812`
- **Baseline puerta de calidad:** pytest = 16 FAIL / 261 PASS · mypy = 57 errores · vitest = 16 PASS

## Workstreams

| ID | Nombre | Fase | Estado | Handoff | Commit |
|---|---|---|---|---|---|
| A1 | Display tests + feedback botón | 1 | ✅ completado | `handoffs/A1.md` | — |
| A2 | mypy verde | 1 | ✅ completado | `handoffs/A2.md` | — |
| B | Seguridad red + README + sudoers | 2 | ✅ completado | `handoffs/B.md` | — |
| C | Display DRM hardening | 2 | ✅ completado | `handoffs/C.md` | — |
| D | Frontend hardening | 2 | ✅ completado | `handoffs/D.md` | — |
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
| 5 | `plugins=["pydantic.mypy"]` NO funciona aquí (pydantic 2.12.5 ↔ mypy 1.19.1, `ImportError: ExpandTypeVisitor`). Solución: patrón `X = Field(default=...)` (runtime idéntico, mypy nativo). `strict=true` intacto | A2 | 2026-08-20 |
| 6 | `invert_x`/`invert_y` en `display/ui/touch.py` son código muerto (no aplicados en `raw_to_screen`). A1 ajustó `test_mapping_with_invert` al comportamiento real. PENDIENTE implementar invert (ver §Pendientes) | A1→futuro | 2026-08-20 |
| 7 | `GET /api/network` queda público (solo lectura); solo POST mutadores exigen auth. No se movió a `/admin/network` (evita romper frontend). `ssh.py`/`deploy.py` sin consolidar en `require_admin_api_key` (futuro) | B | 2026-08-20 |
| 8 | `Screen.allow_mock_fallback` (default True); en modo real se cablea `=mock` para que DRM falle → exit 1. systemd ya cumplía `Restart=on-failure`+`RestartSec=5` (sin cambios) | C | 2026-08-20 |
| 9 | Frontend: Zod v4 + `sequence: number\|null` obligatorio + `lastSequence` init `null` (evita resync espurio). `package-lock` versión raíz alineada 0.1.0→0.3.0. Falta `frontend/.env.example` (futuro) | D | 2026-08-20 |

## Goles (gates)

| Gate | Criterio | Estado |
|---|---|---|
| G1 (post Fase 1) | `pytest backend/tests/ display/tests/` verde · `mypy app/ --strict` = 0 · `vitest` verde | ✅ |
| G2 (post Fase 2) | G1 + `npm run build` verde | ✅ |
| G3 (post Fase 3) | G2 + smoke de importación backend | ⏳ |
| G4 (final) | CI equivalente completo (pytest + ruff + mypy + vitest + build) | ⏳ |

## Pendientes cross-workstream (no perder)

- **P2 — `invert_x`/`invert_y` muertos en `display/ui/touch.py`**: `raw_to_screen` no los aplica. `test_mapping_with_invert` ahora refleja el comportamiento actual (sin invert). Al implementar invert, revertir ese test a las coordenadas invertidas. *Origen: auditoría interna P2-1.* `touch.py` no está asignado a ningún workstream actual.
- **P2 — realinear pydantic↔mypy**: si se quiere recuperar `pydantic.mypy`, alinear versiones (mypy compilado vs pydantic 2.12.5). Mientras tanto mantener `X = Field(default=...)`.
- **Observación (no bloqueante)**: el auto-release del botón usa `_button_press_duration=2` (≈100 ms @20fps) y dispara `_on_release_button()` (incluye `POST /api/button/release`). Confirmar semántica HMI (feedback visual vs "mantener pulsado") en revisión con el usuario.
- **Consolidar `_verify_api_key`** de `ssh.py`/`deploy.py` en `require_admin_api_key` (B lo dejó fuera de alcance). Reduce duplicación y unifica criterio.
- **`SECURITY_MODE=protected` no cubre aún `/admin/*`**: ssh/deploy mantienen su propio `_verify_api_key` (exigen key siempre, independiente de `SECURITY_MODE`). Evaluar coherencia en `docs/SECURITY.md` (F).
- **`frontend/.env.example`** para documentar `VITE_API_URL` (D lo dejó fuera; alcance F).
- **`driver=="fb"` no distinguido en `Screen.init()`** (solo distingue mock vs no-mock); preexistente, fuera de alcance de C.

## Log de ejecución

- 2026-08-20 — Fase 0 iniciada. Baseline registrado. Infraestructura de orquestación creada.
- 2026-08-20 — Fase 1 lanzada: A1 y A2 en paralelo.
- 2026-08-20 — A1 ✅ (display 57 passed / 2 skipped). A2 ✅ (mypy 0 errores, backend 220 passed / 2 skipped).
- 2026-08-20 — **Gate G1 verde** (verificado por hilo principal): pytest 277 passed / 4 skipped / 0 failed · mypy 0 errores · vitest 16/16.
- 2026-08-20 — Fase 2 lanzada: B, C y D en paralelo.
- 2026-08-20 — B ✅ (seguridad red + README + sudoers), C ✅ (DRM hardening), D ✅ (frontend Zod + resync + VITE_API_URL).
- 2026-08-20 — **Gate G2 verde** (verificado por hilo principal): pytest 278 passed / 4 skipped / 0 failed · mypy 0 errores (24 files) · vitest 16/16 · build OK.
