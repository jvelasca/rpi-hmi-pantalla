# FASE 8 · F5 — Ortografía Ñ ("contrasena"→"contraseña") + archivo de legacy `diagnostics/`

Estado de partida: rama `main`, commit `acc42c3`, versión `0.3.4` (objetivo `0.4.0`).
Trabajo aislado y metódico. Sin commit (queda pendiente para el orquestador).

## Resumen

Se corrige la ortografía de todas las variantes de "contrasena" (con N) a
"contraseña" (con Ñ), preservando mayúsculas/minúsculas, en código fuente,
comentarios/docstrings, tests y documentación de alcance.

La tarea de archivar `diagnostics/` **se omite**: la carpeta todavía es
referenciada por tooling de deploy activo (`scripts/setup_rpi.sh` y
`backend/app/services/deploy_service.py`), por lo que moverla rompería el
despliegue. Ver detalle en "Decisiones".

## Archivos modificados (12)

### Frontend

1. `frontend/src/components/SecuritySettings.tsx` — variantes `contrasena`, `Contrasena` y `CONTRASENA` → `contraseña`/`Contraseña`/`CONTRASEÑA` (comentarios, mensajes de error/estado y etiquetas UI).
2. `frontend/src/components/ConfigScreen.tsx` — `Contrasena` → `Contraseña` (comentario de encabezado, sección y etiqueta).
3. `frontend/src/components/LoginScreen.tsx` — `contrasena` y `Contrasena` → `contraseña`/`Contraseña` (comentarios, mensaje y placeholder).
4. `frontend/src/App.tsx` — solo la cadena `"Contrasena incorrecta"` → `"Contraseña incorrecta"`.

### Display

5. `display/app.py` — `contrasena` y `Contrasena` → `contraseña`/`Contraseña` (docstrings y el string de resultado `"Contrasena actualizada"` → `"Contraseña actualizada"`).
6. `display/ui/widgets.py` — variantes `contrasena`, `Contrasena` y `CONTRASENA` → `contraseña`/`Contraseña`/`CONTRASEÑA` (incluye la variable local `contrasena` → `contraseña` y el título `"CONTRASENA"`).
7. `display/ui/theme.py` — `contrasena` → `contraseña` (comentario).
8. `display/tests/test_ui.py` — `contrasena` y `Contrasena` → `contraseña`/`Contraseña` (docstrings y `set_result("Contrasena actualizada")` → `"Contraseña actualizada"`).

### Backend

9. `backend/app/api/ssh.py` — `Contrasena` → `Contraseña` (solo docstring del modelo y `description` de `Field`; sin tocar lógica).
10. `backend/tests/test_migrations.py` — `contrasena` → `contraseña` (solo docstrings).

### Configuración y documentación

11. `.env.example` — `contrasena` y `Contrasena` → `contraseña`/`Contraseña` (comentarios).
12. `docs/ARCHITECTURE.md` — `Contrasena` → `Contraseña` (opción del overlay de CONFIGURACIÓN).

### Nuevo

13. `docs/deploy/handoffs/FASE8_F5_N_LIMPIEZA.md` — este documento.

## Archivos archivados (git mv)

Ninguno. `diagnostics/` **no** se movió a `docs/archive/diagnostics/` (ver "Decisiones").

## Resultado de verificación

- **pytest**: `python -m pytest backend/tests display/tests -q`
  → `393 passed, 9 skipped` (5 warnings preexistentes de corutina no esperada en
  `restore_from_db`, no relacionados con este cambio).
- **ruff**: `python -m ruff check backend display scripts --config backend/pyproject.toml`
  → `All checks passed!`
- **mypy**: `python -m mypy app --config-file pyproject.toml` (desde `backend/`)
  → `Success: no issues found in 31 source files`
- **vitest**: `npm run test` (desde `frontend/`) → `27 passed (3 files)`.
- **build**: `npm run build` (desde `frontend/`) → verde (`tsc -b && vite build`,
  `✓ 103 modules transformed`, sin errores).

## Grep final

No queda ninguna ocurrencia de `contrasena` (con N, cualquier capitalización) en:

- `frontend/src`
- `display/`
- `backend/app`
- `backend/tests`
- `.env.example`
- `docs/ARCHITECTURE.md`

Las únicas menciones restantes son permitidas (registros históricos/meta, no se
tocan por indicación del objetivo):

- `docs/deploy/handoffs/FASE1_*` … `FASE7_*` y `FASE8_*`
  (`FASE7_DISPLAY.md`, `FASE8_F2.1_LED_TITULO.md`, `FASE8_F3_FAIL_CLOSED.md`,
  `FASE8_F4_DRIFT.md`).
- `docs/audits/auditoria-externa-2026-08-21.md`
- `docs/PREMISAS_ESENCIALES.md`

## Decisiones

- **Archivar `diagnostics/`: OMITIDO.** La verificación previa con grep detectó
  referencias activas al directorio `diagnostics/` en árboles dentro del alcance:
  - `scripts/setup_rpi.sh` — ejecuta `$PROJECT_DIR/diagnostics/run_diagnostics.py`
    y `$PROJECT_DIR/diagnostics/gpio/blink_test.py` (tooling de deploy activo).
  - `backend/app/services/deploy_service.py` — `run_diagnostics()` construye la
    ruta remota `{remote_root}/diagnostics/run_diagnostics.py` y
    `{remote_root}/diagnostics/report`.
  - `backend/app/api/deploy.py` — endpoint `GET /admin/deploy/diagnostics` que
    llama a `deploy.run_diagnostics()`.
  - Tests asociados: `backend/tests/test_integration.py` y
    `backend/tests/test_deploy_service.py`.

  Mover `diagnostics/` a `docs/archive/` rompería el flujo de despliegue remoto
  (el diagnóstico es un paso real del deploy y de `setup_rpi.sh`). Por ello se
  salta la tarea B y se deja el directorio en su sitio. No se toca `scripts/`
  (tooling de deploy activo, dentro del alcance de CI de ruff).

- La variable local `contrasena` de `display/ui/widgets.py` se renombró a
  `contraseña` (Python 3 admite `ñ` en identificadores). Ambas apariciones
  (asignación y uso en el f-string) quedan consistentes; pytest/ruff/mypy lo
  confirman.

- En `display/app.py` y `display/tests/test_ui.py` el string `"Contrasena actualizada"`
  se cambió a `"Contraseña actualizada"` de forma coherente (no hay aserciones
  que dependan del literal anterior).

## TEXTO DE PASO

```
Fase 5 del refactor 0.4.0 completada (ortografía Ñ + verificación de archivo de
legacy). Rama main, commit base acc42c3, versión 0.3.4 -> objetivo 0.4.0. Sin commit.

Hecho en esta fase:
- Ortografía: todas las variantes de "contrasena" (con N) -> "contraseña" (con Ñ)
  preservando mayúsculas/minúsculas en frontend (SecuritySettings, ConfigScreen,
  LoginScreen, App), display (app.py, widgets.py, theme.py, test_ui.py), backend
  (ssh.py solo docstrings/description, test_migrations.py solo docstrings),
  .env.example (comentarios) y docs/ARCHITECTURE.md.
- Variable local contrasena -> contraseña en display/ui/widgets.py; título
  CONTRASENA -> CONTRASEÑA; string "Contrasena actualizada" -> "Contraseña
  actualizada" (display/app.py y display/tests/test_ui.py).

Tarea B (archivar diagnostics/): OMITIDA. Grep detectó referencias activas en
scripts/setup_rpi.sh (ejecuta $PROJECT_DIR/diagnostics/run_diagnostics.py y
gpio/blink_test.py) y backend/app/services/deploy_service.py (ruta remota
{remote_root}/diagnostics/...), además del endpoint GET /admin/deploy/diagnostics.
Mover la carpeta rompería el deploy remoto, así que se deja en su sitio.

Verificación:
- pytest backend/tests display/tests: 393 passed, 9 skipped.
- ruff: All checks passed.
- mypy (desde backend/): Success, 31 source files.
- vitest: 27 passed (3 files). npm run build: verde.

Grep final: sin "contrasena" (con N) en frontend/src, display/, backend/app,
backend/tests, .env.example ni docs/ARCHITECTURE.md. Solo queda en handoffs
históricos FASE1_*...FASE7_* y FASE8_*, docs/audits/** y docs/PREMISAS_ESENCIALES.md
(permitidos).

Continuar con la siguiente fase del refactor a 0.4.0.
```
