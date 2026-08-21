# FASE 8 · F1 — Separación de los dos LEDs (refactor 0.4.0)

Estado de partida: rama `main`, commit `2fc44cd`, versión `0.3.4` (objetivo `0.4.0`).

## Resumen

Se separa el control de los dos LEDs físicos:

- **LED principal** (GPIO 20, `role="led"`): lo controla exclusivamente el botón On/Off
  (`toggle_led` / `set_led`).
- **LED del pulsador** (GPIO 21, `role="button_led"`): lo controla exclusivamente el
  pulsador, vía el flag `button.pressed` notificado al callback GPIO.

El bug corregido: `press_button()` invocaba `toggle_led()`, de modo que pulsar el botón
también apagaba/encendía el LED principal de On/Off. Ahora `press_button()` solo
incrementa el contador, marca `pressed=True`, notifica al callback del pulsador
(`("button", True)`), persiste el contador y emite `button_pressed`. No toca
`_led_state` ni emite `led_changed`.

## Archivos modificados

1. `backend/app/services/state_manager.py`
   - `press_button()`: eliminada la llamada `self.toggle_led()` y su comentario asociado.
     Actualizado el docstring para reflejar que ya NO alterna el LED principal.
   - Sin cambios en `toggle_led()`, `set_led()`, `release_button()` ni el resto.

2. `backend/tests/test_state_manager.py`
   - `test_press_button_toggles_led` → `test_press_button_does_not_toggle_led`: ahora
     verifica que `press_button()` NO cambia `led.state` y que sí incrementa
     `press_count` y deja `pressed=True`.

3. `backend/tests/test_hmi.py`
   - `test_press_button_toggles_led` → `test_press_button_does_not_toggle_led`: verifica
     que `POST /api/button/press` NO altera el LED principal.

4. `backend/tests/test_ws_endpoint.py`
   - `test_press_button_emits_led_changed_and_button_pressed` →
     `test_press_button_emits_button_pressed_not_led_changed`: verifica que `press_button`
     emite `button_pressed` y NO emite `led_changed`.

5. `backend/tests/test_integration.py`
   - `test_status_after_changes`: actualizado docstring y comentario (el press ya NO
     alterna el LED; el LED se enciende explícitamente con `/api/led/on`).
   - `test_press_button_broadcasts`: añadida aserción explícita de que el LED permanece
     apagado tras `press_button()`.

No se modificó `display/` ni `frontend/`.

## Resultado de verificación

- **pytest**: `python -m pytest backend/tests display/tests -q`
  → `391 passed, 9 skipped` (5 warnings preexistentes de corutina no esperada en
  `restore_from_db`, no relacionados con este cambio).
- **ruff**: `python -m ruff check backend display scripts --config backend/pyproject.toml`
  → `All checks passed!`
- **mypy**: `python -m mypy app --config-file pyproject.toml` (desde `backend/`)
  → `Success: no issues found in 31 source files`

## Decisiones

- Los tests de `display/tests` no dependían del toggle del LED por `press_button`, por lo
  que no fue necesario tocarlos.
- En `test_state_manager.py` solo `test_press_button_toggles_led` asumía el comportamiento
  incorrecto. El resto de usos de `press_button()` (`test_release_button`,
  `test_multi_press`, tests de callback y `test_concurrent_press_button_no_race`) no
  asertaban cambios de LED, así que se dejaron intactos.
- En `test_ws_endpoint.py` el test nuevo lee un único mensaje tras `press_button` y
  aserta que es `button_pressed` (no `led_changed`), ya que ahora solo se emite un
  broadcast.

## TEXTO DE PASO

```
Fase 1 del refactor 0.4.0 completada (separación de LEDs). Rama main, commit base
2fc44cd, versión 0.3.4 -> objetivo 0.4.0.

Hecho en esta fase:
- backend/app/services/state_manager.py: press_button() ya NO llama a toggle_led().
  Solo incrementa press_count, pone pressed=True, notifica callback del pulsador
  ("button", True), persiste contador y emite button_pressed. Docstring actualizado.
- Tests corregidos: test_state_manager.py, test_hmi.py, test_ws_endpoint.py,
  test_integration.py (press_button ya no alterna el LED principal).

Verificación:
- pytest backend/tests display/tests: 391 passed, 9 skipped.
- ruff: All checks passed.
- mypy (desde backend/): Success, 31 source files.

Sin commit (queda pendiente para el orquestador). No se tocaron SECURITY_MODE,
config.py, security_manager.py, main.py, persistence.py, frontend/ ni display/.

Continuar con la siguiente fase del refactor a 0.4.0.
```
