# FASE 3 — Limpieza de código obsoleto — ENTRADA

- Rama/base: `main` @ `881ec1a` (cambios de Fases 1-2 en working tree, sin commit)
- Versión: 0.3.1
- Alcance: **solo borrado/archivado de código y docs obsoletos + actualización de referencias**. No tocar lógica viva.

## Objetivo

Dejar el repositorio limpio, con un único camino de deploy documentado, sin
`legacy/`, scripts duplicados ni handoffs históricos dispersos. Decisión ya
aprobada por el usuario (ver `docs/PLAN_CIERRE_V1.md` §4): **eliminar
definitivamente** `legacy/`, scripts duplicados y `Rpi_Pantalla_V1.py`.

## Reglas de seguridad (OBLIGATORIAS)

1. **Verificar antes de borrar**: para cada archivo/directorio candidato, haz un
   grep en todo el repo (excluyendo `node_modules/`, `.git/`, `frontend/dist/`,
   `__pycache__/`) de su nombre y de los símbolos que exporta. Solo borra si NO
   hay referencias vivas. Si algo lo referencia (deploy.py, systemd, runbook,
   tests), actualiza primero esa referencia o conserva el archivo.
2. Usar `git rm -r` (o `git rm <archivo>`) para los archivos **trackeados**, de
   modo que la eliminación quede en el índice para un futuro commit. Para
   archivar (mover a `docs/archive/`) usa `git mv`.
3. **NO tocar** (fuera de alcance, prohibido):
   - `backend/` (todo, salvo lo explícito), `display/` (todo), `frontend/src/`,
     `frontend/dist/` (generado).
   - `config/systemd/`, `config/sudoers.d/`, `backend/config/devices.yaml`.
   - `VERSION` (lo exige `release-smoke` de CI), `_version.py`, `pyproject.toml`,
     `requirements.txt`, `package.json`.
   - `.github/`, `.gitignore`, `.gitattributes`, `.env.example`,
     `frontend/.env.example`.
   - `docs/CONTEXT.md`, `docs/SECURITY.md`, `docs/ARCHITECTURE.md`,
     `docs/PLAN_CIERRE_V1.md`, `docs/PREMISAS_ESENCIALES.md`, `docs/PLAN_MAESTRO.md`,
     `docs/deploy/runbook.md`, `docs/deploy/INICIO.md`, `docs/deploy/ESTADO_DESPLEGUE.md`.
   - `README.md`, `LICENSE`, `QUICKSTART.md` (verificar si es vigente antes de decidir).
4. No mezcles fases: si encuentras algo de Fase 4/5 (rate-limiting, versionado),
   anótalo como pendiente y no lo hagas.

## KEEP — camino canónico de deploy (no borrar)

- `scripts/deploy.py` — deploy unificado (referenciado por runbook y README).
- `scripts/deploy_atomic.py` — deploy atómico (runbook §5.1/§5.2 recomienda;
  `--rollback` vive aquí, NO en `rollback.py`).
- `scripts/start_hmi.sh` — referenciado en `docs/CONTEXT.md` (arranque TFT).
- `scripts/setup_rpi.sh` — verificar referencias antes de decidir; si el runbook
  o deploy lo usan, conservar.
- Cualquier archivo que `deploy.py` / `deploy_atomic.py` importen o invoquen.

## DELETE — candidatos (verificar con grep antes de borrar)

### `legacy/` completo (6 archivos)
`README.md`, `static/index.html`, `fb_ui.py`, `fb_probe.py`, `pi_hmi_server.py`,
`hal.py`. Implementación pre-refactor, superada por `backend/` + `display/`.
NOTA: `tests/test_fb_ui.py` (raíz) importa `fb_ui` → borrar ambos juntos.

### Raíz
- `Rpi_Pantalla_V1.py` — script suelto sin uso (verificar).
- `tests/test_fb_ui.py` + `tests/__init__.py` — solo testean `legacy/fb_ui.py`.
  Si el directorio raíz `tests/` queda vacío, eliminarlo.
- `PROMPT_CONTINUACION.md` — instrucción histórica de traspaso (verificar; si
  quedó superada por `docs/CONTEXT.md`, archivar o borrar).

### `scripts/` duplicados / one-off (borrar si no referenciados)
Deploy solapados: `deploy_frontend.py`, `deploy_step.py`, `deploy_display.py`,
`rollback.py` (el `--rollback` real está en `deploy_atomic.py`).
Diagnóstico/one-off Python: `ili9486_driver.py`, `display_probe.py`,
`post_reboot_check.py`, `pi_direct.py`, `pi_display_setup.py`, `recheck.py`,
`recheck2.py`, `diagnose_display.py`, `final_verify.py`, `fix_display.py`,
`install_test.py`, `debug_imports.py`, `final_test.py`, `verify_and_reboot.py`,
`sync_test.py`, `check_deploy.py`, `check_drm_users.py`.
PowerShell one-off: `find_and_connect.ps1`, `full_deploy.ps1`,
`configure_display.ps1`, `configure_display_direct.ps1`, `connect_and_test.ps1`,
`display_check.ps1`, `display_diagnostic.ps1`, `run_configurar_pantalla.ps1`,
`run_diagnostico.ps1`.
Shell/otros: `setup_display.sh`, `setup_venv.sh` (verificar si `setup_rpi.sh` o
runbook los llaman), `touch-fix.dts`, `spidev0.dts`, `ili9486-drm.dts`.

> Regla: si dudas entre borrar o archivar un script, **archívalo** a
> `docs/archive/scripts/` en lugar de borrarlo. El usuario aprobó borrar
> `legacy/` y scripts duplicados; los one-off de diagnóstico que podrían tener
> valor histórico → archivar.

## ARCHIVE — handoffs históricos (mover a `docs/archive/`)

Mover (no borrar) los documentos intermedios ya superados:
- `docs/handoffs/` (CHAT_*.md) → `docs/archive/handoffs/`
- `docs/audits/` (fase*.md, refactor/) → `docs/archive/audits/`
- `docs/deploy/handoffs/H*.md`, `RS_*.md` (históricos, NO los FASE1/FASE2 actuales)
  → `docs/archive/deploy-handoffs/`

Mantener en su sitio: `docs/deploy/handoffs/FASE1_AUTH*.md`,
`docs/deploy/handoffs/FASE2_DOCS*.md` (vigentes), y `docs/deploy/handoffs/FASE3_*.md`
(este trabajo).

## Actualizar referencias si procede

- Si borras scripts referenciados por `docs/deploy/runbook.md`, `README.md`,
  `docs/CONTEXT.md` o `scripts/*.sh`, actualiza esas referencias.
- `ruff` de CI lintea `scripts/`: tras borrar, los scripts restantes deben
  seguir pasando `ruff check scripts/ --config backend/pyproject.toml`. Si alguno
  one-off que conserves falla ruff, corrígelo o archívalo (no dejes ruff roto).

## Verificación final (ejecutar y reportar números)

1. `python -m pytest backend/tests/ display/tests/ -q` → debe quedar verde
   (esperado ~346 passed / 9 skipped; el borrado no debe bajar conteo salvo que
   elimines `tests/test_fb_ui.py` que NO está en esas carpetas).
2. `ruff check backend/ display/ scripts/ --config backend/pyproject.toml` → verde.
3. Simular el `release-smoke` de CI: comprobar que existen `VERSION`,
   `backend/app/main.py`, `backend/config/devices.yaml`, `display/app.py`,
   `config/systemd/rpi-hmi-backend.service`, `config/systemd/rpi-hmi-display.service`;
   y que no hay `__pycache__`/`.pyc`/`.env` (solo `.env.example`).
4. `git status --short` final limpio (sin `__pycache__` ni artefactos).

## Entregable

Escribe `docs/deploy/handoffs/FASE3_LIMPIEZA_CIERRE.md` con: resumen factual,
lista EXACTA de archivos borrados (git rm) vs archivados (git mv), resultado de
cada verificación (pytest/ruff/smoke con números), decisiones, pendientes/fuera
de alcance, y un bloque "TEXTO DE PASO" para la Fase 4 (hardening y mejoras
menores: rate-limiting login, resolución display, `.gitattributes`/sudoers).

Devuélveme en tu respuesta final: (1) resumen, (2) archivos borrados vs
archivados, (3) resultado de pytest/ruff/smoke, (4) pendientes. No commits git.
