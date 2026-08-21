# FASE 5 — Verificación final y cierre (bump 0.3.2) — CIERRE

- Rama/base: `main` @ `881ec1a` (working tree con Fases 1-5, **sin commit**)
- Versión: **0.3.1 → 0.3.2** (bump coherente en los 7 sitios, verificado)
- Resumen: última fase del cierre de V1. Bump de versión 0.3.1 → 0.3.2 en los 7 sitios,
  limpieza de los 3 pendientes heredados de Fase 4, verificación final completa (toda
  verde) y documentación de cierre. No se hizo commit (el orquestador decidirá el commit
  final y el deploy a la Pi).

## Cambios

### MODIFICADOS (9)

- `VERSION` — `0.3.1` → `0.3.2`.
- `backend/app/_version.py` — `_FALLBACK = "0.3.1"` (línea 15) → `"0.3.2"`.
- `backend/pyproject.toml` — `version = "0.3.1"` → `"0.3.2"`.
- `pyproject.toml` (raíz) — `version = "0.3.1"` → `"0.3.2"`; y en
  `[tool.pytest.ini_options]` `norecursedirs` retirado `"legacy"` (ya no existe el
  directorio): `["legacy", ".venv", ...]` → `[".venv", ...]`.
- `frontend/package.json` — `"version": "0.3.1"` → `"0.3.2"`.
- `frontend/package-lock.json` — `"version": "0.3.1"` → `"0.3.2"` en las **2** líneas del
  paquete raíz (líneas 3 y 9). Los deps transitivos (`@jridgewell/*` `0.3.12`/`0.3.13`)
  no se tocaron.
- `display/app.py` — fallback de `_load_version()` (línea 92) `return "0.3.1"` → `"0.3.2"`.
  (La versión real sigue leyéndose de `VERSION`; este literal es solo el fallback.)
- `docs/CONTEXT.md` — actualizadas las secciones de estado actual (ver más abajo).
- `docs/deploy/INICIO.md` — referencias a `QUICKSTART.md` (borrado en Fase 4) apuntadas a
  `docs/deploy/runbook.md` en el mapa de workstreams H5 (tabla de propiedad y detalle H5);
  la tabla de auditoría P2-6 (hallazgo histórico) se deja intacta.

### CREADO (1)

- `docs/deploy/handoffs/FASE5_CIERRE_FINAL.md` — este documento (sobrescribe la ENTRADA).

### Detalle de la edición en `docs/CONTEXT.md` (solo secciones de estado actual, sin reescribir historia)

- `Última sesion`: fecha 2026-08-21, Versión `0.3.2`, "cierre de V1 — Fases 1-5 completadas".
- Tabla `Estado actual` → fila `Tests`: **353 pytest + 26 vitest**.
- `Tareas pendientes`: nueva subsección "Cierre de V1 (PLAN_CIERRE_V1.md) — COMPLETADO"
  (Fases 1-5 `[x]`) + "Pendientes del hilo principal/orquestador" (deploy a la Pi + commit
  final) + "Construcción original (histórico)" (la lista anterior conservada tal cual).
- `Archivos creados/modificados (fase 3)`: eliminada la línea `scripts/deploy_frontend.py`.

## Verificación (números reales, ejecutados 2026-08-21)

| Gate | Comando | Resultado | Estado |
|---|---|---|---|
| pytest | `python -m pytest backend/tests/ display/tests/ -q` | **353 passed / 9 skipped / 5 warnings** (84.49 s) | 🟢 |
| ruff | `ruff check backend/ display/ scripts/ --config backend/pyproject.toml` | **All checks passed!** | 🟢 |
| mypy | `python -m mypy app/ --config-file pyproject.toml` (desde `backend/`) | **Success: no issues found in 28 source files** | 🟢 |
| bandit | `bandit -r backend/app display --exclude backend/tests,display/tests -q --severity-level medium` | **exit 0** (0 issues medium+; 1 warning `nosec` por B104 ya documentado) | 🟢 |
| pip-audit | `pip-audit -r backend/requirements.txt` | **No known vulnerabilities found** | 🟢 |
| vitest | `npm run test` (frontend) | **26 passed (26)** / 3 files | 🟢 |
| build | `npm run build` (frontend) | **`rpi-hmi-frontend@0.3.2` · ✓ built in 2.06s** (102 modules) | 🟢 |
| npm audit | `npm audit --audit-level=high` (frontend) | **found 0 vulnerabilities** | 🟢 |
| release-smoke | simulación CI | `VERSION=0.3.2` semver válido; 7 archivos requeridos presentes; sin `__pycache__`/`.pyc`/`.env` **trackeados en git** | 🟢 |

Notas de la simulación `release-smoke`:

- Archivos requeridos presentes: `VERSION`, `backend/app/main.py`,
  `backend/config/devices.yaml`, `display/app.py`, `frontend/dist/index.html`,
  `config/systemd/rpi-hmi-backend.service`, `config/systemd/rpi-hmi-display.service`.
- Archivos prohibidos: se verificó con `git ls-files` que **no hay** `__pycache__`,
  `*.pyc` ni `.env` trackeados (todos gitignored). En el working tree local existen
  artefactos de desarrollo (`backend/__pycache__/`, `.mypy_cache`, `.pytest_cache`,
  `.ruff_cache`, `.coverage`, `.env` local) que **no** se commitean y no aparecerían en
  el checkout limpio de CI.

## Decisiones

1. **Bump manual (sin `npm version`).** Se editó `package-lock.json` con
   `StrReplace` acotado a `"version": "0.3.1"` (solo líneas 3 y 9; no afecta a los deps
   transitivos `0.3.12`/`0.3.13`). Motivo: determinismo y evitar que `npm version`
   genere un commit/tag (regla: no commits). Verificado con grep `0\.3\.2` en los 7 sitios.
2. **No hay test de coherencia de versión.** Se buscó en `backend/tests/` y
   `display/tests/` (grep `VERSION|_version|0.3.1`) y no existe ningún test que compare
   contra `"0.3.1"`. El único gate de versión es el CI `release-smoke`, que valida
   semver por regex (`^[0-9]+\.[0-9]+\.[0-9]+$`) y `0.3.2` lo cumple. **Nada que ajustar.**
3. **`scripts/deploy_atomic.py` no se tocó.** Contiene `0.3.1` solo como ejemplos
   ilustrativos en docstring/help (líneas 7, 8, 33, 344: `releases/0.3.1`,
   `--version 0.3.1`, "e.g. 0.3.1"), no como pin de versión real (la versión se lee de
   `VERSION`). No es uno de los 7 sitios; se deja y se reporta como limpieza opcional.
4. **`docs/ARCHITECTURE.md` y `docs/SECURITY.md` NO se tocaron** (están en la lista
   NO-tocar). Ambas mantienen `0.3.1` en su cabecera de versión
   (`ARCHITECTURE.md` línea 1 "v0.3.1" y línea 211; `SECURITY.md` línea 7). Se reporta
   al orquestador para que decida si actualiza esas cabeceras (son docs vivos, no
   históricos).
5. **`docs/deploy/ESTADO_DESPLEGUE.md` NO se editó.** Su cabecera declara
   "ÚNICO editor de este archivo: el hilo principal". Es un registro histórico H1-H9
   ya cerrado y no está roto. El orquestador lo actualizará si lo estima.
6. **`docs/deploy/INICIO.md`**: se corrigieron SOLO las referencias de archivo del mapa
   H5 (tabla de propiedad + detalle) de `QUICKSTART.md` → `docs/deploy/runbook.md`, para
   no dejar una referencia rota. La tabla de auditoría P2-6 se deja intacta por ser
   evidencia histórica del hallazgo (en ese momento `QUICKSTART.md` existía).

## Pendientes / fuera de alcance (para el orquestador)

- **Deploy físico a la Pi con 0.3.2** — pendiente (scripts `scripts/deploy*.py` +
  `docs/deploy/runbook.md` ya listos; resta ejecutar el despliegue con la versión nueva).
- **Commit final de las Fases 1-5** — el orquestador decide el commit (regla: no commits
  de subagentes). El working tree acumula las 5 fases sin commit.
- **Cabeceras de versión `0.3.1` en `docs/ARCHITECTURE.md` y `docs/SECURITY.md`** — docs
  NO-tocar; el orquestador decide si las actualiza a `0.3.2`.
- **`scripts/deploy_atomic.py`** con `0.3.1` en ejemplos de docstring/help — limpieza
  opcional (no es pin de versión).
- Los handoffs históricos (`docs/deploy/handoffs/FASE1-4_*.md`), `docs/PREMISAS_ESENCIALES.md`,
  `docs/PLAN_CIERRE_V1.md` y `docs/PLAN_FASE2.md` conservan `0.3.1` como referencia al
  estado previo al bump — referencias históricas legítimas, no se tocan.

## TEXTO DE PASO FINAL (cierre del proyecto — pegar donde corresponda)

"Proyecto RPi HMI cerrado (V1). Working tree en `main` @ `881ec1a` con las 5 fases del
plan de cierre aplicadas **sin commit**. Versión final **0.3.2** coherente en los 7 sitios
(`VERSION`, `backend/app/_version.py`, `backend/pyproject.toml`, `pyproject.toml` raíz,
`frontend/package.json`, `frontend/package-lock.json` líneas 3 y 9, `display/app.py`
línea 92). Verificación final TODA VERDE: pytest 353 passed / 9 skipped · ruff 'All
checks passed!' · mypy 0 issues (28 files) · bandit exit 0 · pip-audit sin vulnerabilidades
· vitest 26/26 · build `rpi-hmi-frontend@0.3.2` · npm audit 0 vulnerabilidades ·
release-smoke OK (VERSION semver válido + archivos requeridos presentes + sin artefactos
prohibidos trackeados). Limpieza de pendientes: `docs/CONTEXT.md` (estado actual +
`deploy_frontend.py` retirado), `docs/deploy/INICIO.md` (QUICKSTART→runbook) y
`norecursedirs` sin `'legacy'`. Estado de las fases: Fase 1 (auth session-cookie) ✅,
Fase 2 (docs) ✅, Fase 3 (limpieza) ✅, Fase 4 (hardening) ✅, Fase 5 (verificación + bump)
✅. Pendientes solo para el orquestador: (1) deploy físico a la Pi con 0.3.2, (2) commit
final de las 5 fases, (3) opcional: actualizar cabeceras de versión en
`docs/ARCHITECTURE.md`/`docs/SECURITY.md` (NO-tocar para subagentes) y ejemplos
ilustrativos de `scripts/deploy_atomic.py`. Lee `docs/deploy/handoffs/FASE5_CIERRE_FINAL.md`
y `docs/PREMISAS_ESENCIALES.md`."
