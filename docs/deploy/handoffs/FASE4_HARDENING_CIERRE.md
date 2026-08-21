# FASE 4 — Hardening y mejoras menores — CIERRE

- Rama/base: `main` @ `881ec1a` (working tree con Fases 1-3 sin commit)
- Versión: 0.3.1 (el bump a 0.3.2 es de la **Fase 5**, NO se hizo)
- Resumen: añadido rate-limiting en memoria al login (anti brute-force), corregido el
  árbol de `scripts/` en `ARCHITECTURE.md`, eliminado el scaffolding de Visual Studio
  (`.pyproj`/`.slnx`) y `QUICKSTART.md`, centralizada la resolución de display en el
  setting `DISPLAY_RESOLUTION`, y verificados `.gitattributes`, sudoers,
  `ESTADO_DESPLEGUE.md` y `README.md`. Sin commits git.

## Cambios

### MODIFICADOS (9 + 2 untracked de Fase 1)

- `backend/app/api/auth.py` — añadido `LoginRateLimiter` (ventana fija en memoria por
  IP, stdlib `threading`+`time`), helper `_client_ip`, singleton `rate_limiter`, y
  aplicado el rate-limit en `POST /api/auth/login` (cuenta solo fallos; 429 al
  superar el límite; login correcto resetea). Docstrings Google-style en español.
  (Archivo untracked creado en Fase 1; editado en esta fase.)
- `backend/app/config.py` — nuevos settings con `Field` + docstring y validación:
  `login_max_attempts` (int, default 5, `ge=1`), `login_window_seconds` (int, default
  300, `ge=10`) y `display_resolution` (str, default "480x320", `pattern=r"^\d+x\d+$"`).
  Añadidas las 3 variables al docstring del módulo.
- `backend/app/main.py` — los dos `set_display` de la detección de display usan ahora
  `settings.display_resolution` en lugar de `"480x320"` hardcodeado.
- `backend/app/services/state_manager.py` — `set_display(resolution=None)` resuelve
  `settings.display_resolution` cuando no se pasa resolución (default centralizado).
- `backend/tests/test_auth.py` — nueva clase `TestLoginRateLimit` (4 tests): 429 por
  exceso, reset tras login correcto, ventana expirada permite reintentar, clave
  correcta no bloqueada. Fixture `clear_sessions` ampliado para limpiar el
  rate-limiter. (Archivo untracked creado en Fase 1; editado en esta fase.)
- `backend/tests/test_config.py` — defaults nuevos en `test_default_values` y 3 tests
  de validación (patrón `display_resolution`, `login_max_attempts ge=1`,
  `login_window_seconds ge=10`).
- `docs/ARCHITECTURE.md` — árbol de `scripts/`: sustituidos `deploy_step.py`,
  `deploy_frontend.py`, `rollback.py` y el `... (*.ps1, *.dts)` por los 4 reales
  (`deploy.py`, `deploy_atomic.py`, `start_hmi.sh`, `setup_rpi.sh`). Verificado que
  no quedan referencias a otros archivos borrados en Fase 3.
- `docs/SECURITY.md` — añadidas `LOGIN_MAX_ATTEMPTS`/`LOGIN_WINDOW_SECONDS` en §3,
  nota de rate-limiting en §2 y una línea en el checklist de producción §7.
- `.env.example` — documentadas `LOGIN_MAX_ATTEMPTS`, `LOGIN_WINDOW_SECONDS` y
  `DISPLAY_RESOLUTION` (nueva sección "Display").

### ELIMINADOS (`git rm`, 3 archivos)

- `QUICKSTART.md` — desactualizado y solapado con README + runbook.
- `Rpi_Pantalla_V1.pyproj` — scaffolding Visual Studio obsoleto (referenciaba
  `Rpi_Pantalla_V1.py`, ya borrado).
- `Rpi_Pantalla_V1.slnx` — idem.

### CREADOS (1)

- `docs/deploy/handoffs/FASE4_HARDENING_CIERRE.md` — este documento.

### VERIFICADOS SIN CAMBIO

- `.gitattributes` — correcto (`eol=lf` para `config/systemd/*.service`,
  `config/sudoers.d/*`, `*.sh`). No se tocó.
- `config/sudoers.d/rpi-hmi` — correcto (regla mínima `pi NOPASSWD /usr/bin/nmcli`).
  No se tocó.
- `docs/deploy/ESTADO_DESPLEGUE.md` — NO se tocó: su cabecera declara "ÚNICO editor
  de este archivo: el hilo principal". Es un registro histórico (H1-H9) de la fase
  de despliegue anterior, no está roto. Se reporta sin cambios.
- `README.md` — verificado: no referencia archivos borrados en Fase 3 (el árbol de
  `scripts/` ya lista los 4 reales; "rollback" solo aparece como descripción de
  `deploy_atomic.py`, que existe). No se tocó.

## Verificación

- **pytest** `python -m pytest backend/tests/ display/tests/ -q`:
  **353 passed / 9 skipped / 5 warnings** (84.51 s) — verde.
  (Baseline Fase 3 = 346 passed / 9 skipped; +7 tests nuevos: 4 de rate-limit +
  3 de validación de settings.)
- **ruff** `python -m ruff check backend/ display/ scripts/ --config backend/pyproject.toml`:
  **All checks passed!** — verde.
- **npm run build** (frontend): no ejecutado (no se tocó `frontend/`; no obligatorio).
- **git status --short**: sin artefactos (`__pycache__`/`.pyc`/`.pytest_cache`/
  `.ruff_cache`/`.mypy_cache`) — verificado con grep sobre la salida.

## Decisiones

1. **Rate-limit del login (in-memory, stdlib).** Ventana fija por IP de cliente que
   cuenta SOLO intentos fallidos; superado `LOGIN_MAX_ATTEMPTS` dentro de
   `LOGIN_WINDOW_SECONDS` devuelve 429; login correcto resetea el contador. Todo en
   memoria (`threading.Lock` + `time.monotonic`) y sin dependencias nuevas, coherente
   con el rechazo previo de `itsdangerous`. El reloj es inyectable (`clock`) para
   testear la expiración de ventana. Se usa `request.client.host` (sin
   `X-Forwarded-For`, porque la topología documentada no tiene proxy inverso).
2. **`QUICKSTART.md` eliminado.** `grep QUICKSTART` muestra referencias solo en
   documentos históricos (`docs/archive/*` y `docs/deploy/INICIO.md`, mapa de
   workstreams de una fase ya cerrada), no en ningún documento vivo (README, runbook,
   CONTEXT, ARCHITECTURE, SECURITY). El contenido útil ya está en README + runbook.
   Se elimina y se documenta aquí.
3. **`docs/deploy/ESTADO_DESPLEGUE.md` NO se edita.** Su cabecera reserva la edición
   al hilo principal; se deja intacto (registro histórico, no roto).
4. **Resolución de display = mejora mínima.** Se centraliza en `DISPLAY_RESOLUTION`
   sin refactorizar el layout proporcional de `display/` (que ya escala respecto a
   480x320). El default se mantiene `"480x320"`, por lo que no cambia comportamiento.

## Pendientes / fuera de alcance

- **`docs/CONTEXT.md` (NO-tocar)** — en la sección "Archivos creados/modificados
  (fase 3)" (línea ~294) aún menciona `scripts/deploy_frontend.py`. Es NO-tocar
  salvo necesidad estricta; se deja y se reporta para que el hilo principal decida.
- **`docs/deploy/INICIO.md`** — mapa de workstreams histórico (fase H1-H9 ya cerrada)
  que menciona `QUICKSTART.md` en tablas de auditoría/H5. No es documento vivo; se
  deja intacto (reescribirlo sería reescribir historia).
- **`pyproject.toml` (raíz)** — `norecursedirs` aún contiene `"legacy"` (heredado de
  Fase 3; inofensivo). NO-tocar.
- **Bump a `0.3.2`** y **suite final completa** (mypy, bandit, pip-audit, vitest,
  npm build, npm audit): **Fase 5**, fuera del alcance de esta fase.

## TEXTO DE PASO (pegar en el siguiente chat)

"Proyecto RPi HMI en `main` @ `881ec1a` (working tree con Fases 1-4, sin commit).
Fase 4 (hardening y mejoras menores) completada: rate-limiting del login en memoria
(`LoginRateLimiter`, ventana fija por IP, solo fallos, 429 al superar, reset en
login correcto; settings `LOGIN_MAX_ATTEMPTS=5` y `LOGIN_WINDOW_SECONDS=300`);
corregido árbol de `scripts/` en ARCHITECTURE.md; eliminados con `git rm`
`QUICKSTART.md`, `Rpi_Pantalla_V1.pyproj` y `Rpi_Pantalla_V1.slnx`; centralizada la
resolución de display en `DISPLAY_RESOLUTION` (config.py + main.py +
state_manager.set_display). Verificados sin cambio `.gitattributes`, sudoers,
`ESTADO_DESPLEGUE.md` (lo edita solo el hilo principal) y README. Verificación:
pytest 353 passed / 9 skipped · ruff 'All checks passed!' · git sin artefactos.
Pendientes: CONTEXT.md menciona `deploy_frontend.py` (NO-tocar), INICIO.md histórico
menciona QUICKSTART, `norecursedirs` con 'legacy'. Siguiente fase: Fase 5 —
verificación final completa (pytest, ruff, mypy, bandit, pip-audit, vitest, build,
npm audit), coherencia de versión y bump a 0.3.2 + cierre. Lee
`docs/deploy/handoffs/FASE4_HARDENING_CIERRE.md`."
