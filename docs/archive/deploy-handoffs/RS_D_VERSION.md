# Handoff RS_D — Versión de la app desde VERSION (fuente única)

## Resultado
Completado. El fichero `VERSION` (raíz del repo, contenido `0.3.0`) pasa a ser la
**fuente única de la versión de la aplicación**, leída en runtime por backend y
display. Se eliminó la duplicación hardcodeada de `0.3.0` en los dos puntos de
backend y los dos puntos de display. No se añadió `setuptools_scm`, ni plugins,
ni pipeline de release.

## Qué cambió

- Se creó `backend/app/_version.py`: loader que lee `VERSION` desde
  `Path(__file__).resolve().parents[2] / "VERSION"` y expone `__version__: str`
  con fallback seguro a `"0.3.0"` (`try/except OSError`).
- En `backend/app/main.py` se importa `__version__` y se sustituye en:
  - `FastAPI(..., version=__version__)` (antes `version="0.3.0"`).
  - `JSONResponse(..., "version": __version__)` del endpoint raíz `/`.
- En `display/app.py` se añadió un loader equivalente a nivel de módulo (raíz
  del repo = `Path(__file__).resolve().parents[1]`), más el import de `pathlib`.
  Se usa `__version__` en:
  - `HeaderWidget(..., version=__version__)` (antes `version="0.3.0"`).
  - Banner `logger.info("  RPi HMI — Display App Pygame DRM v%s", __version__)`
    con formateo lazy `%s` (sin f-strings en logging).

## Archivos tocados

- `backend/app/_version.py` — [nuevo] loader de versión.
- `backend/app/main.py` — [editado] 1 import + 2 líneas de versión.
- `display/app.py` — [editado] import `Path` + loader + 2 líneas de versión.
- `frontend/package.json` — [sin cambios] verificado en `0.3.0` (sin drift).

No se tocó `VERSION`, `pyproject.toml`, `backend/pyproject.toml`,
`frontend/package-lock.json`, la versión de protocolo WebSocket `"1.0"`, ni la
lógica del worker REST de `display/app.py`.

## Nota sobre frontend

El frontend **no muestra la versión en la UI** hoy. Su fuente de versión es
`frontend/package.json` (metadato de build), que ya está en sync con `VERSION`
(`0.3.0`). No se añadió `define` de Vite ni código muerto.

## Verificación ejecutada (gate) — desde la raíz del repo

1. `python -m ruff check backend/ display/`

```
All checks passed!
```

2. `python -m mypy backend/app/ --config-file backend/pyproject.toml`

```
Success: no issues found in 27 source files
```

3. `python -m pytest backend/tests/ display/tests/ -q`

```
============================= test session starts =============================
platform win32 -- Python 3.13.7, pytest-8.4.2, pluggy-1.6.0
PyQt6 6.10.2 -- Qt runtime 6.10.1 -- Qt compiled 6.10.0
rootdir: E:\SINCRONIZADO\Informatica\Proyectos VisualStudio\Python\Rapsberry\Rpi_Pantalla_V1
configfile: pyproject.toml
plugins: anyio-4.12.1, asyncio-1.4.0, cov-7.0.0, mock-3.15.1, qt-4.5.0
asyncio: mode=Mode.AUTO, debug=False, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function
collected 341 items

... (resumen) ...
============ 332 passed, 9 skipped, 5 warnings in 87.08s (0:01:27) ============
```

## Texto de paso al siguiente agente
`VERSION` ya es la fuente única de la versión en backend (`_version.py`) y
display (loader a nivel de módulo); gate verde (`ruff` limpio, `mypy` sin issues,
`332 passed / 9 skipped / 0 failed`). Frontend sigue tomando su versión de
`package.json` (build), en sync con `VERSION`.
