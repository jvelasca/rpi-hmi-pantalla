# FASE 8 / F6 — Bump a 0.4.0 + verificación final — CIERRE

Estado de partida: rama `main`, commit `cf18dd0`, versión `0.3.4` (objetivo `0.4.0`).
Trabajo aislado y metódico. Sin commit (queda pendiente para el orquestador).

## Cambios

### Bump de versión (0.3.4 → 0.4.0)

1. `VERSION` — `0.3.4` → `0.4.0` (una sola línea, sin saltos extra).
2. `pyproject.toml` — `version = "0.3.4"` → `version = "0.4.0"`.
3. `backend/pyproject.toml` — `version = "0.3.4"` → `version = "0.4.0"`.
4. `backend/app/_version.py` — `_FALLBACK = "0.3.4"` → `_FALLBACK = "0.4.0"` (sin tocar la lógica de lectura de `VERSION`).
5. `display/app.py` — en `_load_version()` el fallback `return "0.3.4"` → `return "0.4.0"` (sin tocar nada más del fichero).
6. `frontend/package.json` — `"version": "0.3.4"` → `"version": "0.4.0"`.
7. `frontend/package-lock.json` — DOS apariciones `"version": "0.3.4"` → `"0.4.0"` (paquete raíz, línea 3, y `packages[""]`, línea 9). Sin tocar versiones de dependencias.

### Documentación con referencia a versión "actual"

8. `docs/ARCHITECTURE.md` — título `(v0.3.4)` → `(v0.4.0)` y línea del árbol `├── VERSION  # Versión única del proyecto (0.3.4)` → `(0.4.0)`.
9. `docs/SECURITY.md` — línea 7 `Versión del proyecto: 0.3.4` → `0.4.0`.
10. `docs/CONTEXT.md` — `Branch: main · Versión 0.4.0`; sección "Ultima sesion" actualizada (cierre de Fase 8 F0-F6, verificación real y "Siguiente: HIL en Pi real"); fila `Tests` de "Estado actual" con números reales.
11. `docs/PREMISAS_ESENCIALES.md` — línea 6 a `Versión del proyecto: 0.4.0 · Estado: refactor Fase 8 COMPLETADO (pendiente HIL en Pi real)`; sección "9. Trabajo actual" marca F0-F6 como completadas con línea de cierre.

### Nuevo

12. `docs/deploy/handoffs/FASE8_F6_CIERRE.md` — este documento.

## Verificación

- **pytest**: `python -m pytest backend/tests/ display/tests/ -q`
  → `393 passed, 9 skipped` (5 warnings preexistentes de corutina no esperada en
  `restore_from_db`, no relacionados con este cambio).
- **ruff**: `python -m ruff check backend/ display/ scripts/ --config backend/pyproject.toml`
  → `All checks passed!`
- **mypy**: `python -m mypy app/ --config-file pyproject.toml` (desde `backend/`)
  → `Success: no issues found in 31 source files`
- **vitest**: `npm run test` (desde `frontend/`) → `27 passed (3 files)`.
- **build**: `npm run build` (desde `frontend/`) → verde (`tsc -b && vite build`,
  `✓ 103 modules transformed`).
- **npm audit**: `npm audit --audit-level=high` → `found 0 vulnerabilities`.
- **bandit**: `python -m bandit -r backend/app display --exclude backend/tests,display/tests -q --severity-level medium`
  → exit 0, sin issues de severidad medium+ (solo warning benigno
  `nosec encountered (B104)` en `backend/app/config.py:58`).
- **pip-audit**: `python -m pip_audit -r backend/requirements.txt -r display/requirements.txt`
  → `No known vulnerabilities found`.
- **semver `VERSION`**: valida `^[0-9]+\.[0-9]+\.[0-9]+$` → `0.4.0` OK.

## Grep final de restos `0.3.4`

Sin ocurrencias de `0.3.4` en código, `VERSION`, `pyproject.toml`,
`backend/pyproject.toml`, `backend/app/_version.py`, `display/app.py`,
`frontend/package.json`, `frontend/package-lock.json`, ni en documentación
"actual" (`ARCHITECTURE.md`, `SECURITY.md`, `CONTEXT.md`, `PREMISAS_ESENCIALES.md`).

Las únicas ocurrencias restantes son **históricas permitidas** (no se tocan):

- `docs/deploy/handoffs/FASE8_F1_LED.md`, `FASE8_F2_UI.md`, `FASE8_F2.1_LED_TITULO.md`,
  `FASE8_F3_FAIL_CLOSED.md`, `FASE8_F4_DRIFT.md`, `FASE8_F5_N_LIMPIEZA.md`
  (líneas de "Estado de partida" y "TEXTO DE PASO").
- `docs/deploy/handoffs/FASE7_CIERRE.md` (líneas 3 y 66).
- `docs/audits/baseline-2026-08-21.md` y `docs/audits/auditoria-externa-2026-08-21.md`.
- `docs/CONTEXT.md` línea de changelog histórico ("F7 cierre (0.3.4)").

## Decisiones

- La versión se **centraliza en `VERSION`** (raíz); `backend/app/_version.py` y
  `display/app.py` la leen en runtime y solo conservan un fallback sincronizado
  (`0.4.0`) para el caso de fichero ausente.
- Se mantienen los fallbacks `0.4.0` en `_version.py` y `display/app.py` para no
  romper el arranque si `VERSION` no está presente.
- **No se toca documentación histórica**: handoffs `FASE8_F1`…`F5`, `FASE7_CIERRE.md`,
  `docs/audits/*` y el changelog de `docs/CONTEXT.md` conservan sus referencias a
  `0.3.x` como registro histórico.
- Sin commit ni push (el orquestador revisa y commitea).

## Pendientes / fuera de alcance

- **HIL en Raspberry Pi real**: apagado brusco, SQLite corrupta, touch, DRM,
  login/logout, validación del display físico con 0.4.0.
- Commit/push de este cierre: pendiente del orquestador.
- Ninguna herramienta quedó "no disponible localmente": bandit, pip-audit y
  npm-audit se ejecutaron y pasaron en local.

## TEXTO DE PASO (pegar en el siguiente chat)

```
Fase 8 / F6 completada: bump 0.3.4 -> 0.4.0 + verificación final + cierre documental.
Rama main, commit base cf18dd0, versión 0.3.4 -> 0.4.0. Sin commit (pendiente orquestador).

Hecho en esta fase:
- Bump a 0.4.0 en: VERSION, pyproject.toml, backend/pyproject.toml,
  backend/app/_version.py (_FALLBACK), display/app.py (fallback _load_version),
  frontend/package.json y frontend/package-lock.json (2 apariciones).
- Docs "actuales" actualizadas a 0.4.0: docs/ARCHITECTURE.md (título + árbol VERSION),
  docs/SECURITY.md (línea 7), docs/CONTEXT.md (Branch, sección Ultima sesion,
  fila Tests) y docs/PREMISAS_ESENCIALES.md (línea 6 + sección 9 marca F0-F6 completadas).
- Nuevo handoff: docs/deploy/handoffs/FASE8_F6_CIERRE.md.

Verificación:
- pytest backend/tests display/tests: 393 passed, 9 skipped.
- ruff: All checks passed. mypy (backend/): Success, 31 source files.
- vitest: 27 passed (3 files). npm run build: verde (103 modules).
- npm audit: 0 vulnerabilidades. bandit: exit 0 (sin issues medium+).
- pip-audit: sin vulnerabilidades conocidas. VERSION semver: 0.4.0 OK.

Grep final: sin 0.3.4 en código/paquetes/docs actuales. Solo queda en históricos
permitidos (handoffs FASE8_F1..F5, FASE7_CIERRE.md, docs/audits/* y changelog de
docs/CONTEXT.md).

Siguiente fase: HIL en Raspberry Pi real (apagado brusco, SQLite corrupta, touch,
DRM, login/logout...). Lee docs/deploy/handoffs/FASE8_F6_CIERRE.md para el detalle.
```
