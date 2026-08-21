# FASE 4 — Hardening y mejoras menores — ENTRADA

- Rama/base: `main` @ `881ec1a` (cambios de Fases 1-3 en working tree, sin commit)
- Versión: 0.3.1 (el bump a 0.3.2 es de la **Fase 5**, NO tuyo)
- Alcance: hardening puntual + mejoras menores + resolver pendientes de Fase 3.

## Reglas de gobernanza (OBLIGATORIAS)

- Lee `docs/PREMISAS_ESENCIALES.md` (gobernanza) y `docs/PLAN_CIERRE_V1.md` §3 Fase 4.
- Lee el handoff de cierre de Fase 3: `docs/deploy/handoffs/FASE3_LIMPIEZA_CIERRE.md`
  (contiene los pendientes que heredas).
- No mezcles fases: el versionado 0.3.2 y la suite final completa son de Fase 5.
- Todo cambio de código debe llevar docstring (estilo Google en español, coherente
  con el resto) y test nuevo/actualizado.
- Documenta en `/docs` donde corresponda (SECURITY.md, .env.example) en el MISMO
  cambio.
- No commits git.

## Tareas (por orden)

### 1. Rate-limiting del login (anti brute-force) — PRINCIPAL
- Añade un rate-limiter **en memoria, stdlib** (sin dependencias nuevas; el
  proyecto ya rechazó `itsdangerous` por ese motivo) al endpoint
  `POST /api/auth/login` en `backend/app/api/auth.py`.
- Diseño mínimo recomendado: ventana fija por IP de cliente; contar SOLO los
  intentos fallidos; el login correcto reinicia el contador de esa IP; superado el
  límite devuelve **429** con `{"detail": ...}`.
- Nuevos settings en `backend/app/config.py` (con `Field` + docstring y validación):
  - `LOGIN_MAX_ATTEMPTS` (int, default `5`, `ge=1`)
  - `LOGIN_WINDOW_SECONDS` (int, default `300`, `ge=10`)
- Documenta ambas variables en `.env.example` y en `docs/SECURITY.md` (sección de
  variables y/o checklist de producción).
- Tests nuevos en `backend/tests/test_auth.py`: exceso de intentos → 429; login
  correcto tras varios fallidos resetea; ventana expirada permite reintentar;
  (opcional) que el límite no rompe el flujo normal con clave correcta.

### 2. Corregir árbol de `scripts/` en `docs/ARCHITECTURE.md`
- Líneas ~196-198 aún listan `deploy_step.py`, `deploy_frontend.py`, `rollback.py`
  (borrados en Fase 3). Sustitúyelos por los 4 reales: `deploy.py`,
  `deploy_atomic.py`, `start_hmi.sh`, `setup_rpi.sh`.
- Revisa el resto del árbol de `ARCHITECTURE.md` y corrige cualquier otra
  referencia a archivos borrados en Fase 3.

### 3. Eliminar scaffolding de Visual Studio
- `Rpi_Pantalla_V1.pyproj` y `Rpi_Pantalla_V1.slnx` referencian `Rpi_Pantalla_V1.py`
  (ya borrado). Bórralos con `git rm` (verifica antes con grep que nada los usa).

### 4. QUICKSTART.md
- Está desactualizado (referencia `backend/app/hardware/hal.py`, `backend/app/domain/`,
  `api/devices.py`, Python 3.8+, `diagnostics/gpio/blink_test.py` como si fuera la
  vía principal, y "LED en pin 17" cuando el LED es virtual) y solapa
  `README.md` + `docs/deploy/runbook.md`.
- Decisión: **eliminarlo** (`git rm`) si ningún documento vivo lo referencia
  (grep `QUICKSTART`); si algo lo referencia, actualiza esa referencia. El
  contenido útil ya está en README + runbook.

### 5. Resolución de display (mínimo, no sobre-ingeniería)
- La resolución `"480x320"` está hardcodeada en `backend/app/main.py` (detección de
  display, dos `set_display`) y como default en `backend/app/services/state_manager.py`
  (`set_display(resolution="480x320", ...)`).
- Mejora MÍNIMA: centraliza en un único setting `DISPLAY_RESOLUTION` (str, default
  `"480x320"`, patrón `^\d+x\d+$`) en `config.py`, úsalo en `main.py` (ambos
  `set_display`) y como default de `state_manager.set_display`. Documenta en
  `.env.example`.
- NO refactorices el layout proporcional de `display/app.py` ni `display/ui/*`
  (ya escala respecto a 480x320); no lo toques salvo que sea trivial y seguro.
- Ajusta los tests afectados (`test_main_lifespan.py`) si cambia el default.

### 6. Verificar (sin cambio salvo que esté roto)
- `.gitattributes` (LF en systemd/sudoers/*.sh) — ya correcto; reporta.
- `config/sudoers.d/rpi-hmi` (regla mínima nmcli) — ya correcto; reporta.
- `docs/deploy/ESTADO_DESPLEGUE.md` — verifica que refleje el estado final (auth por
  cookie, SECURITY_MODE, limpieza); actualiza solo si está desactualizado.
- `README.md` — verifica que no referencia archivos borrados en Fase 3.

## NO tocar (fuera de alcance)
`VERSION`, `_version.py`, `pyproject.toml`, `requirements.txt`, `package.json`,
`.github/`, `backend/config/devices.yaml`, `config/systemd/`, `docs/CONTEXT.md`
(salvo si es estrictamente necesario y documentado), `docs/SECURITY.md` salvo para
añadir las variables del rate-limit, `docs/PLAN_CIERRE_V1.md`, `PREMISAS_ESENCIALES.md`.

## Verificación final (ejecutar y reportar números reales)
1. `python -m pytest backend/tests/ display/tests/ -q` — verde (esperado ≥ 346
   passed; sumará los tests nuevos del rate-limit).
2. `ruff check backend/ display/ scripts/ --config backend/pyproject.toml` — verde.
3. `npm run build` en `frontend/` — verde (por si tocas algo de docs solo, debería
   seguir igual; no es obligatorio si no tocas frontend).
4. `git status --short` final sin artefactos.

## Entregable
Escribe `docs/deploy/handoffs/FASE4_HARDENING_CIERRE.md` con: resumen factual,
lista EXACTA de archivos modificados/creados/eliminados, resultados de pytest/ruff
con números, decisiones (incluida la del rate-limit y la de QUICKSTART), pendientes/
fuera de alcance, y bloque "TEXTO DE PASO" para la Fase 5 (verificación final +
bump 0.3.2 + cierre).

Devuélveme en tu respuesta final: (1) resumen, (2) archivos tocados, (3) resultados
pytest/ruff, (4) decisiones y pendientes.
