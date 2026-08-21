# Handoff H6 — Scaffolding de tests HIL (Hardware-In-the-Loop)

## Resultado
Completado. Creado el scaffolding de tests HIL marcados con `@pytest.mark.hardware`
y auto-saltados (skip) en entornos sin hardware (Windows/CI). Registrado el marker
`hardware` en los dos `pyproject.toml` para que `--strict-markers` no falle. Los 5
tests se saltan en Windows; en la Pi solo corren con `RPI_HIL=1`.

## Archivos modificados
- `backend/tests/test_hil_hardware.py` — [nuevo] 5 tests HIL: gpiomem, DRM card0,
  health, api/status y touch. Skip a nivel de modulo si `RPI_HIL!=1`, y skip por
  recurso ausente en cada test.
- `pyproject.toml` — [editado] marker `hardware` registrado en `[tool.pytest.ini_options]`.
- `backend/pyproject.toml` — [editado] marker `hardware` registrado en `[tool.pytest.ini_options]`.
- `docs/deploy/handoffs/H6-hil.md` — [nuevo] este handoff.

## Verificación ejecutada
Ejecutado desde la raiz del repo (salvo mypy, desde `backend/`):

- `python -m pytest backend/tests/test_hil_hardware.py -q` -> **5 skipped** (0 fail, 0 error).
- `python -m pytest backend/tests/test_hil_hardware.py -q --collect-only` -> **5 tests
  collected**, sin errores de marker (`hardware` registrado correctamente).
- `python -m ruff check backend/tests/test_hil_hardware.py --config backend/pyproject.toml`
  -> **All checks passed** (0 errores).
- `cd backend && python -m mypy tests/test_hil_hardware.py --config-file pyproject.toml`
  -> **Success: no issues found** (0 errores).

## Decisiones tomadas
- Doble barrera de skip: `skipif` a nivel de modulo con `RPI_HIL=1` (corte grueso en
  Windows/CI) + `pytest.skip` por test cuando el dispositivo o endpoint concreto no
  esta presente (corte fino en una Pi con hardware parcial). Asi nunca hay fallo duro
  por ausencia de hardware.
- Deteccion de touch reimplementada via sysfs (`/sys/class/input/<event>/device/name`)
  en lugar de importar `evdev` (no instalado en Windows), reutilizando la misma lista
  de palabras clave (`touch`, `ads7846`, `xpt`, `ft5x`, `gt9`, `stmpe`) de
  `display/ui/touch.py`.
- HTTP con stdlib `urllib.request` (`timeout=5.0`). Distincion de errores:
  `HTTPError` -> `pytest.fail` (el backend respondio pero mal = fallo real);
  `URLError`/`OSError` -> `pytest.skip` (sin conexion = no aplica).
- Misma entrada de marker en ambos `pyproject.toml`; el resto de la seccion
  `[tool.pytest.ini_options]` queda intacto.

## Riesgos / pendientes
- `/health` y `/api/status` asumen el backend en `localhost:8000`. Si en la Pi corre
  en otro puerto, esos tests se saltan (conexion rechazada) en vez de fallar.
- `/dev/fb1` (framebuffer SPI) aparece en el contexto pero no estaba en la lista de
  tests requeridos; no se testea. Si se quiere cubrir el display via framebuffer,
  anadir un test analogo a `test_drm_card0_exists`.
- El skip por recurso ausente implica que un HIL "verde" no garantiza que TODO el
  hardware este presente. En una Pi completa se debe revisar que el numero de skipped
  sea 0 (los endpoints exigen el backend levantado).

## Texto de paso al siguiente agente
Workstream H6-hil completo y verificado: 5 skipped en Windows, marker `hardware`
registrado en ambos `pyproject.toml`, y ruff + mypy limpios. Para ejecutar los HIL en
la Pi fisica:

```bash
RPI_HIL=1 python -m pytest backend/tests/test_hil_hardware.py -q
```

En una Pi completa se esperan 5 passed / 0 skipped, con el backend levantado en
`localhost:8000` para los dos tests HTTP.
