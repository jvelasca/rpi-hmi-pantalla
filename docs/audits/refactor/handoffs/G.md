# Handoff G — Lint ruff (0 errores) + pin versión

## Resultado
Completado (no parcial). El comando de CI `python -m ruff check backend/ display/ scripts/ --config backend/pyproject.toml` pasa de **206 errores** a **0 errores**, y ruff queda pineado a **`==0.16.3`** en `backend/pyproject.toml` y `.github/workflows/ci.yml`.

- 126 correcciones aplicadas con `ruff --fix` (F401, I001, W292, F541, UP*, etc.).
- 74 correcciones manuales (B008, B904, B905, B007, E501, E402, SIM102/SIM105/SIM115/SIM117, F821, F841, N806).
- Suite verde: pytest **278 passed / 4 skipped**, mypy **0 issues**, frontend build **OK**.

## Archivos modificados
Todos [editado], salvo indicación. La mayoría son auto-fix (imports/orden/anotaciones); los marcados con `*` tuvieron edición manual además.

Config:
- `backend/pyproject.toml` — `ruff>=0.8` → `ruff==0.16.3`
- `.github/workflows/ci.yml` — `pip install ruff>=0.8` → `pip install ruff==0.16.3`

Backend (app):
- `backend/app/api/deploy.py` * (B008 noqa)
- `backend/app/api/ssh.py` * (E501, SIM105, B904, B008 noqa, E402→import arriba)
- `backend/app/api/ws.py` * (SIM105)
- `backend/app/main.py` * (E501)
- `backend/app/models/hmi.py` * (E501)
- `backend/app/services/deploy_service.py` * (SIM105, E501)
- `backend/app/services/network_service.py` * (E501 x3)
- `backend/app/services/ssh_manager.py` * (SIM105 x4)
- `backend/app/services/state_manager.py` * (B007)
- `backend/__init__.py`, `backend/app/__init__.py`, `backend/app/api/__init__.py`
- `backend/app/api/deps.py`, `backend/app/api/health.py`
- `backend/app/models/__init__.py`, `backend/app/models/device.py`, `backend/app/models/events.py`
- `backend/app/services/__init__.py`, `backend/app/services/gpio_service.py`, `backend/app/services/persistence.py`

Backend (tests):
- `backend/tests/test_integration.py` * (SIM117)
- `backend/tests/test_main_lifespan.py` * (F841, E501 x2)
- `backend/tests/test_persistence.py` * (N806)
- `backend/tests/conftest.py`, `backend/tests/test_config.py`, `backend/tests/test_deploy_service.py`
- `backend/tests/test_gpio_service.py`, `backend/tests/test_hmi.py`, `backend/tests/test_models.py`
- `backend/tests/test_ssh_manager.py`, `backend/tests/test_state_manager.py`, `backend/tests/test_ws_endpoint.py`

Display:
- `display/app.py` * (E501, SIM102)
- `display/ui/touch.py` * (N806 x12, SIM105)
- `display/ui/widgets.py` * (E402, B905 x2, E501, B007, SIM105, F821)
- `display/ui/screen.py` (F401)
- `display/tests/test_ui.py` * (SIM117 x2)

Scripts:
- `scripts/deploy.py` * (E402 noqa, E501)
- `scripts/deploy_atomic.py` * (E402 noqa, F821→VENV_PIP, F841 x3, E501)
- `scripts/rollback.py` * (E402 noqa)
- `scripts/ili9486_driver.py` * (SIM115 noqa)
- `scripts/deploy_frontend.py` (F541), `scripts/display_probe.py` (F401)

## Verificación ejecutada
- `python -m ruff check backend/ display/ scripts/ --config backend/pyproject.toml` → **All checks passed!** (0 errores)
- `python -m pytest backend/tests/ display/tests/ -q` → **278 passed, 4 skipped** (1 warning preexistente de coroutine no awaited)
- `cd backend && python -m mypy app/ --config-file pyproject.toml` → **Success: no issues found in 25 source files**
- `cd frontend && npm run build` → **built in 560ms** (verde; frontend no tocado)

## Decisiones tomadas
- **B008** en firmas de endpoints FastAPI (`Depends(...)`, `Security(...)`): falsos positivos del patrón de inyección de dependencias estándar de Starlette. Se añadió `# noqa: B008` en cada línea. NO se cambió la firma.
- **E402** en `scripts/deploy.py`, `scripts/deploy_atomic.py`, `scripts/rollback.py`: los imports de `backend.app...` deben ir *después* de `load_dotenv(...)` porque los módulos de backend leen `settings` del entorno al importar. Se justificó con `# noqa: E402` + comentario. En `ssh.py` el import de `dotenv` sí se movió arriba (era side-effect free).
- **F821** en `display/ui/widgets.py`: `ERROR` (color rojo) está definido en `theme.py` pero no se importaba → bug real. Se añadió `ERROR` al `from display.ui.theme import (...)`.
- **F821** en `scripts/deploy_atomic.py`: `VENV_PIP` no definido → bug real. Se añadió `VENV_PIP = f"{PI_BASE}/venv/bin/pip3"` a la sección de paths (junto a `VENV_PY`).
- **SIM115** en `scripts/ili9486_driver.py`: el fd SPI debe permanecer abierto durante toda la vida del objeto; `with open(...)` lo cerraría y rompería el driver → `# noqa: SIM115` con comentario.
- **B905** (`zip`): se usó `strict=False` en todos los casos (equivalente exacto al comportamiento previo; no fuerza igualdad de longitudes).
- **B904**: `raise ... from exc` en todos los `except`.
- **N806**: variables matemáticas renombradas a snake_case (`S_rx2`→`s_rx2`, etc.; `M`→`m` en `_solve3`).
- **F841/B007**: eliminadas variables muertas (`steps`, `release`, `result` sin uso, `mock_updater`) o `_` en loops.
- **SIM102/SIM117**: colapsados ifs/withs anidados (combinando condiciones con `and` y context managers con `(...)`).

## Riesgos / pendientes
- `VENV_PIP` se resolvió como binario `pip3` del venv. Si la intención original era `{VENV_PY} -m pip`, ajustar en `scripts/deploy_atomic.py` (el nombre de la variable sugiere binario pip3, que es lo estándar).
- `strict=False` en `zip` es la opción conservadora; si se confirma que las listas siempre tienen igual longitud, podría usarse `strict=True` (cambiaría runtime si no coinciden).
- `docs/audits/refactor/ESTADO.md`, `README.md`, `docs/SECURITY.md` y `frontend/.env.example` ya aparecían modificados antes de este workstream; NO se tocaron (fuera de mi alcance).
- Frontend NO se modificó.

## Texto de paso al siguiente agente
Workstream de lint/pin completado. No queda trabajo de lint pendiente en `backend/`, `display/`, `scripts/` (ruff 0 errores con ruff 0.16.3). Si el siguiente agente toca código Python, debe mantener `python -m ruff check backend/ display/ scripts/ --config backend/pyproject.toml` en 0 y no revertir los `# noqa: B008`/`# noqa: E402`/`# noqa: SIM115` justificados.
