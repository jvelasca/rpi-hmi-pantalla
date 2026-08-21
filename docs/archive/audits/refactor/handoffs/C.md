# Handoff C — Display: fallback DRM→mock sin silencio + detección de conector

## Resultado
Separado el fallback de `Screen.init()` para que el modo real (no `--mock`) **no** caiga silenciosamente a mock cuando DRM falla. En producción, si DRM falla → `init()` devuelve `False` → `DisplayApp.run()` devuelve `1` → systemd reinicia. La detección de display ahora lee el estado real del conector DRM vía `/sys/class/drm/card0-*/status` con fallback seguro a `fb1` y luego `mock`, sin romper el caso PC (Windows/sin DRM sigue resolviendo a mock). Estado final de `display/tests/`: 58 passed, 2 skipped, 0 failed.

## Archivos modificados
- `display/ui/screen.py` [editado]
  - `Screen.__init__`: nuevo parámetro `allow_mock_fallback: bool = True`; almacenado como `self.allow_mock_fallback`.
  - `Screen.init()` (bloque `except`): el fallback a mock solo se ejecuta si `self.allow_mock_fallback and not self.mock`; en caso contrario devuelve `False`.
  - Nueva helper `_drm_connector_state() -> str` que devuelve `"connected"` / `"disconnected"` / `"unknown"` leyendo `/sys/class/drm/card0-*/status` (tolerante a `OSError` y a ausencia de sysfs).
  - `_detect_display()`: si `/dev/dri/card0` existe, usa `_drm_connector_state()`; solo resuelve a `"drm"` con estado `"connected"` o `"unknown"`. Con estado `"disconnected"` continúa al fallback `fb1` → `mock`.
- `display/app.py` [editado]
  - Construcción de `Screen` en `DisplayApp.__init__`: ahora pasa `allow_mock_fallback=mock` (modo real `False`, modo mock/dev `True`). No se tocó el feedback del botón ni ningún otro bloque.
- `display/tests/test_ui.py` [editado]
  - `TestScreenDRMFallback.test_screen_initializes_mock_when_drm_unavailable`: reescrito para ejercitar el fallback real (parchea `screen._init_drm` y verifica `init() is True` + `screen.mock is True`).
  - Añadido `TestScreenDRMFallback.test_screen_returns_false_when_drm_fails_without_fallback` (verifica `init() is False` + `screen.mock is False` con `allow_mock_fallback=False`).
- `config/systemd/rpi-hmi-display.service` — **sin cambios**: ya tenía `Restart=on-failure` y `RestartSec=5` (verificado, ambos correctos).

## Verificación ejecutada
- `python -m pytest display/tests/ -q` (desde la raíz) → `58 passed, 2 skipped` (0 failed).
- `python -c "import display.ui.screen; print('ok')"` → imprime `ok` (exit 0).

## Decisiones tomadas
1. **`allow_mock_fallback` por defecto `True`** para no cambiar el contrato de `Screen` para el resto de callers (tests y uso mock/dev siguen funcionando igual). Solo el camino de producción lo desactiva explícitamente.
2. **`allow_mock_fallback=mock` en `app.py`**: en modo real (`mock=False`) queda `False`; en mock/dev (`mock=True`) queda `True`, tal como pide el enunciado. Es una expresión directa porque `mock` ya es `bool`.
3. **`_drm_connector_state` usa `"unknown"` como señal de "intentar DRM"**: si `card0` existe pero el sysfs no es legible o no hay ficheros `status`, se mantiene el comportamiento anterior (intentar DRM) en vez de degradar a mock por error. Solo un `"disconnected"` explícito degrada a `fb1`/`mock`.
4. **Fallback de detección**: con `card0` presente pero conector `"disconnected"`, se cae a `fb1` (framebuffer ILI9486) antes que a mock, respetando la prioridad documentada del proyecto.
5. **No se tocó `config/systemd/rpi-hmi-display.service`**: ya cumple el requisito (`Restart=on-failure`, `RestartSec=5`). Un `exit 1` de `run()` dispara reinicio.

## Riesgos / pendientes
- La lectura de `/sys/class/drm/card0-*/status` solo se ejercita en Linux con DRM; en este entorno Windows los tests no la cubren con un sysfs real (no aplica: `_detect_display` devuelve `mock`). Se validó por inspección de código, no por test de integración en la Pi.
- El path de detección `"disconnected"` → `fb1` no está cubierto por tests unitarios; sería útil un test con `patch` de `Path.exists`/`glob`, pero `Path` se usa como objeto importado y parchearlo es frágil. No bloqueante.
- El fallback a `fb1` en `_init_drm`/`init` sigue sin ruta específica de driver: `driver == "fb"` no se distingue en `init()` (solo distingue `mock` vs "no mock"), igual que antes de este workstream. Fuera del alcance asignado.

## Texto de paso al siguiente agente
Workstream C completo y verde. No queda trabajo pendiente dentro del alcance (`display/ui/screen.py`, `display/app.py` solo wiring de `Screen`, `config/systemd/rpi-hmi-display.service`, y tests de `Screen`). Para el orquestador: registrar que el servicio systemd ya cumplía `Restart=on-failure` + `RestartSec=5` (sin cambios). No revertir el `allow_mock_fallback=False` del modo real: es lo que garantiza `exit 1` sin mock silencioso en producción.
