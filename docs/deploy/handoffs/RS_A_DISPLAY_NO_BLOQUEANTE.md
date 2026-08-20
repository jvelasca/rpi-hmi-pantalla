# Handoff RS_A — Display sin bloqueo REST en el bucle de Pygame

## Resultado
Completado. Se elimino el bloqueo del bucle de Pygame (`run()`) y de los callbacks
táctiles causado por llamadas REST síncronas (`requests.get/post` con timeout 2-5s).
Ahora toda peticion HTTP se encola en un unico worker thread daemon y se ejecuta en
background, de modo que si el backend/red se cuelga, la pantalla ya no se congela
durante el timeout.

## Que cambio
- **Antes**: `_api_get`, `_api_post` y `_api_post_json` ejecutaban `requests.*` de
  forma síncrona y devolvían el resultado. Se invocaban desde `_on_toggle_led`,
  `_on_press_button`, `_on_release_button`, `_apply_network`, `_apply_font_settings`,
  `_fetch_network`, `_fetch_font_settings`, `_sync_state` y el `run()` (sync inicial,
  carga de fuente y sync periódico de fallback).
- **Despues**:
  - Nuevo worker thread daemon (`display-rest`) + `queue.Queue` (`_rest_queue`).
  - `_api_get/_api_post/_api_post_json` ahora encolan la peticion y retornan
    inmediatamente (no bloquean). Aceptan un callback opcional `on_result`.
  - El worker ejecuta la peticion HTTP (`_request_get/_request_post/_request_post_json`)
    y actualiza `self.backend_connected` bajo `self._ws_lock` (mismo lock del hilo WS).
  - Los resultados que requieren tocar widgets se devuelven via una cola de UI
    (`_rest_ui_queue`) y se aplican en el hilo principal con `_apply_rest_results()`
    (llamado cada iteracion del bucle), evitando tocar pygame desde el worker.
  - `_sync_state()` deja de bloquear: encola un GET `/api/status` y aplica el estado
    en el hilo principal (mismos campos: `led_on`, `led_label`, `press_count`,
    `ws_connected` y los widgets).
  - `_fetch_network`, `_apply_network` y `_fetch_font_settings` usan `on_result` para
    actualizar sus vistas en el hilo principal.
  - Shutdown limpio: `cleanup()` activa `_rest_stop` y hace `join(timeout=1.0)` del
    worker; usa `getattr` para no romper instancias creadas via `__new__` en tests.

## Archivos tocados (exclusiva)
- `display/app.py` — [editado] se anade `import queue` y
  `from collections.abc import Callable`; se agrega estado del worker en `__init__`;
  se reemplaza la seccion de comunicacion REST por los metodos no bloqueantes; se
  adaptan `_fetch_network`, `_apply_network`, `_fetch_font_settings`, `_sync_state`,
  `run()` (carga de fuente, sync periodico, drenado de resultados, lectura de
  `backend_connected` bajo lock) y `cleanup()`.
- `docs/deploy/handoffs/RS_A_DISPLAY_NO_BLOQUEANTE.md` — [nuevo] este handoff.

No se modifico `display/tests/test_display_app.py` (los tests existentes siguen
pasando sin cambios) ni ningun archivo de `backend/` ni `display/ui/*`. El sistema
WebSocket (`_ws_loop`, `_start_ws_thread`, `on_open/on_message/on_error/on_close`,
`_apply_ws_state`) queda intacto.

## Verificacion ejecutada (salida real del gate)
Desde la raiz del repo:

1. `python -m pytest display/tests/ -q` -> **verde** (0 failed).

```
============================= test session starts =============================
platform win32 -- Python 3.13.7, pytest-8.4.2, pluggy-1.6.0
PyQt6 6.10.2 -- Qt runtime 6.10.1 -- Qt compiled 6.10.0
rootdir: E:\SINCRONIZADO\Informatica\Proyectos VisualStudio\Python\Rapsberry\Rpi_Pantalla_V1
configfile: pyproject.toml
plugins: anyio-4.12.1, asyncio-1.4.0, cov-7.0.0, mock-3.15.1, qt-4.5.0
asyncio: mode=Mode.AUTO, debug=False, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function
collected 66 items

display\tests\test_display_app.py ...............s.                      [ 25%]
display\tests\test_ui.py ............................................s.. [ 96%]
..                                                                       [100%]

======================== 64 passed, 2 skipped in 0.42s ========================
```

2. `python -m ruff check display/` -> **limpio**.

```
All checks passed!
```

## Riesgos / pendientes
- La sincronizacion periodica de fallback ya no compara `old_led`/`old_count` de forma
  síncrona (imposible al ser async); el redibujado lo dispara el callback `on_result`
  de `_sync_state` via `_redraw`, con lo que la actualizacion visual puede retrasarse
  un frame respecto a la version anterior. No afecta a la semantica del estado.
- `backend_connected` ahora lo escribe el worker bajo `_ws_lock`; la lectura en la
  status bar tambien se protege con el lock. Es un `bool`, por lo que la carrera
  residual (si existiera) es inocua.
- El worker procesa las peticiones FIFO, preservando el orden POST -> sync que ya
  existia (p. ej. `_on_toggle_led`).
- La verificacion `requests.get(.../health)` en `main()` (una sola vez, antes del
  bucle) se mantiene síncrona por estar fuera del alcance ("bucle de Pygame"); si se
  quiere eliminar ese bloqueo de arranque, es un pendiente menor separado.
- No se anadieron tests nuevos para el worker porque la instruccion solo permitia
  editar `display/app.py`; la cobertura existente sigue verde.
