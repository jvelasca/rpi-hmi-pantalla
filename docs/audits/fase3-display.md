# FASE 3 — Display: thread-safety, rendimiento, touch robusto ✅ COMPLETADA

**Fecha:** 2026-08-11
**Tests:** 116/116 pasando (107 originales + 9 nuevos)
**Resultado:** Thread-safety corregida con lock consistente, touch evdev ahora despacha a widgets, botón usa feedback no-bloqueante (frame-based), código muerto eliminado

---

## Cambios realizados

### 1. 🔴 Thread-safety — lock consistente entre WS thread y main loop

**Problema:** El hilo WebSocket escribía `led_on`, `led_label`, `press_count` y mutaba directamente los widgets (`self.led.on`, `self.led.label`, `self.button.press_count`) fuera del lock en `on_message`. El main loop leía estos mismos atributos sin lock en `_sync_state()` y el bucle principal.

**Solución:**

| Antes | Ahora |
|-------|-------|
| WS thread mutaba estado compartido y widgets sin lock | WS thread escribe solo estado compartido bajo `_ws_lock` y activa flag `_ws_dirty` |
| Main loop leía `ws_connected` sin lock | Main loop lee `ws_connected` bajo `_ws_lock` |
| Widgets mutados desde el hilo WS | `_apply_ws_state()` (solo hilo principal) copia estado bajo lock y lo aplica a widgets fuera del lock |

**Archivo:** `display/app.py`

- `on_message`: todas las escrituras a `led_on`, `led_label`, `press_count` ocurren dentro de `with self._ws_lock`, y se activa `self._ws_dirty = True`. Eliminada la mutación directa de widgets.
- `_apply_ws_state()`: nuevo método que lee el estado bajo lock, copia a variables locales, y aplica a widgets fuera del lock. Retorna `True` si hubo cambios.
- Main loop: `ws_connected` se lee bajo `with self._ws_lock` al actualizar la status bar.

### 2. 🔴 Touch — conexión de callbacks evdev a dispatch de widgets

**Problema:** `TouchHandler.poll()` se llamaba en el bucle principal, pero los callbacks `on_touch_down`, `on_touch_up`, `on_touch_move` nunca se conectaban. Los eventos táctiles reales del driver evdev se leían pero se descartaban silenciosamente. Solo funcionaba el touch en modo mock (vía `MOUSEBUTTONDOWN` de Pygame).

**Solución:**

| Antes | Ahora |
|-------|-------|
| `TouchHandler` sin callbacks conectados | `on_touch_down`, `on_touch_up`, `on_touch_move` conectados en `__init__` |
| Touch real en Pi no funcionaba | `_handle_touch_down` → `_dispatch_touch` → `widget.on_touch()` |

**Archivo:** `display/app.py`

- En `DisplayApp.__init__`: cuando `self.touch.available`, se conectan los tres callbacks:
  - `self.touch.on_touch_down = self._handle_touch_down`
  - `self.touch.on_touch_up = self._handle_touch_up`
  - `self.touch.on_touch_move = self._handle_touch_move`
- `_handle_touch_down(screen_x, screen_y)`: delega en `_dispatch_touch`.
- `_handle_touch_up` y `_handle_touch_move`: stubs (la UI actual solo usa touch-down).

### 3. 🟠 Rendimiento — feedback de botón no bloqueante

**Problema:** `_on_press_button` llamaba a `_render()` + `screen.flip()` + `time.sleep(0.08)`, bloqueando el main loop durante ~80ms. Esto causaba micro-congelaciones en la UI y retrasaba el procesamiento de eventos táctiles.

**Solución:**

| Antes | Ahora |
|-------|-------|
| `time.sleep(0.08)` bloqueante + render/flip forzado | Contador de frames `_button_press_frame` con duración configurable |
| Feedback visual inmediato pero bloqueante | Feedback visual no-bloqueante: el botón se libera tras N frames en el bucle principal |

**Archivo:** `display/app.py`

- `_on_press_button`: fija `self.button.pressed = True` y `self._button_press_frame = 0`. Sin sleep ni render forzado.
- Main loop: cada frame incrementa `_button_press_frame`. Al alcanzar `_button_press_duration` (2 frames), libera `self.button.pressed = False`.
- `_button_press_duration = 2`: con FPS=20, equivale a ~100ms de feedback visual (similar al sleep original de 80ms).

### 4. 🟡 Limpieza — código muerto y variables no usadas

**Eliminado:**
- `_ws_pending_updates: list[dict]` — definido en `__init__` pero nunca usado.
- `from pathlib import Path` — import no usado en `app.py`.
- `touch_pending = False` — variable declarada pero nunca usada en el bucle principal.
- `dt = self.screen.tick(...)` — valor no usado; se mantiene la llamada a `tick()` para control de FPS.

---

## Archivos modificados (2)

| Archivo | Tipo de cambio |
|---------|---------------|
| `display/app.py` | Thread-safety, touch callbacks, feedback no-bloqueante, limpieza |
| `display/tests/test_ui.py` | +9 tests para thread-safety, touch dispatch, button feedback |

---

## Nuevos tests (9)

### Thread-safety (3 tests)

| Test | Qué valida |
|------|-----------|
| `test_apply_ws_state_no_dirty_returns_false` | `_apply_ws_state` retorna `False` si `_ws_dirty` es `False` |
| `test_apply_ws_state_applies_led_changes` | Estado WS se copia bajo lock y se aplica a widgets; dirty flag se limpia |
| `test_apply_ws_state_no_changes_returns_false` | Sin cambios reales, retorna `False` (dirty flag igual se limpia) |

### Touch dispatch (3 tests)

| Test | Qué valida |
|------|-----------|
| `test_handle_touch_down_dispatches_to_led` | Touch en área del botón toggle del LED activa el callback on_toggle |
| `test_handle_touch_down_dispatches_to_button` | Touch en centro del botón principal activa el callback on_press |
| `test_handle_touch_down_miss_no_dispatch` | Touch fuera de widgets no activa ningún callback |

### Button feedback (3 tests)

| Test | Qué valida |
|------|-----------|
| `test_button_press_sets_frame_counter` | `_on_press_button` fija `pressed=True` y `_button_press_frame=0` |
| `test_button_feedback_releases_after_duration` | El botón se libera tras `_button_press_duration` frames |
| `test_button_feedback_does_not_release_early` | El botón no se libera antes de la duración configurada |

---

## Verificación

- `python -m pytest backend/tests/ display/tests/ -v --tb=short` → **116 passed**
- Sin linter errors en los 2 archivos modificados
- Los 107 tests existentes siguen pasando sin cambios

---

## Próxima fase: FASE 4 — Deploy/CI

**Prompt para el siguiente chat:**

> Continuamos el plan de trabajo consolidado para el proyecto Rpi_Pantalla_V1 (Raspberry Pi HMI).
>
> Las FASE 0 (Seguridad), FASE 1 (Arquitectura), FASE 2 (Estado/eventos) y FASE 3 (Display) están completadas — 116/116 tests pasando.
> Los documentos de cierre están en:
> - `docs/audits/fase0-seguridad.md`
> - `docs/audits/fase1-arquitectura.md`
> - `docs/audits/fase2-estado-eventos.md`
> - `docs/audits/fase3-display.md`
> - `docs/audits/plan-consolidado.md`
>
> Ahora ejecuta la FASE 4 — Deploy/CI: GitHub Actions, rollback, artefactos.
> Revisa `docs/audits/plan-consolidado.md` para los detalles de la fase.
>
> IMPORTANTE:
> - Lee los archivos relevantes antes de modificar nada
> - Ejecuta los tests (`python -m pytest backend/tests/ -v --tb=short`) después de cada cambio
> - Si algo rompe, arréglalo antes de continuar
> - No modifiques nada que no esté en esta lista
