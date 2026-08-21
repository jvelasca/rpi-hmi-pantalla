# FASE 7c — Menú de contraseña en el display físico (Pygame)

Estado de partida: Fase 7a/7b ya aplicada (backend). El backend ya expone:

- `GET /api/auth/security` → `{ "enabled": bool, "is_default": bool }`.
- `POST /api/auth/security` → body `{ "enabled": bool, "current": str|null }`.
  - `401` si no autorizado (sin cookie ni X-API-Key y `current` incorrecto).
  - `409` si `enabled=true` y la contraseña sigue siendo la de fábrica (`1234`).
  - `200` con `{enabled, is_default}` si ok.
- `POST /api/auth/password` → body `{ "current": str, "new": str }`; `new` mínimo **8 caracteres** (si no, `422`).

El display físico (Pygame) se comunica por REST vía el worker no bloqueante de
`display/app.py` (`_api_get`, `_api_post_json`) contra `localhost:8000`
(loopback → exento de auth para mutadores HMI, pero los endpoints de seguridad
NO tienen exención loopback: requieren `current`).

## Objetivo

Añadir un menú "Contraseña" al overlay de CONFIGURACION del display físico,
que permita ver el estado (activada/desactivada y de fábrica/personalizada),
activar/desactivar la protección y cambiar la contraseña, usando un **teclado
numérico en pantalla** para introducir texto.

## Reglas de UX (muy importante)

- Si el usuario intenta **activar** y `is_default` es `true`, el display NO debe
  llamar a la API: debe mostrar el error
  "Debes cambiar la contraseña de fábrica (1234) antes de activar"
  (el backend devuelve 409 como defensa en profundidad, pero el display hace la
  comprobación en cliente porque su capa REST pierde el código de estado).
- La contraseña nueva debe tener **mínimo 8 caracteres**; validar en cliente.
- El teclado es **numérico** (0-9) + `BORRAR` (quitar último dígito) + `LIMPIAR`.
  Limitación documentada: desde la pantalla física solo se pueden introducir
  contraseñas numéricas; para contraseñas alfanuméricas usar la web.

## Cambios en `display/ui/widgets.py`

### 1. `ConfigOverlay`: añadir 6ª opción "Contraseña"

- `n = 5` → `n = 6`; añadir `self._btn_security` (rect) en la posición
  correspondiente (antes de "Volver", que debe quedar último).
- Ajustar `btn_h`/`gap`/`start_y` si es necesario para que quepan 6 botones en
  480x320 (verificar que el último botón no se salga de pantalla).
- `set_callbacks(...)`: añadir el parámetro `security` (callback). Reordenar
  firma: `(screen_test, touch_calib, network, font, security, back)`.
- `draw(...)`: dibujar el nuevo botón con un icono de candado
  (`_ICON_LOCK = "\U0001F512"` no vale en fuentes bitmap; usar un glifo simple
  disponible, p. ej. "*" o reutilizar el icono existente). Define un
  `OPTION_ICON_LOCK` en `display/ui/theme.py` si hace falta.
- `on_touch(...)`: despachar `_btn_security`.

### 2. Nueva clase `SecuritySettingsView(Widget)`

Sigue el patrón de `NetworkConfigView`/`FontSettingsView` (hit-regions +
callbacks). Debe tener:

- `set_on_back(callback)`, `set_on_toggle(callback)`, `set_on_change(callback)`,
  `set_status(dict)` (recibe `{enabled, is_default}`), `set_result(msg, error)`.
- Estado interno: campos editables `current`, `new`, `confirm`; un campo activo
  (`_active_field`); el teclado numérico escribe en el campo activo.
- Draw:
  - Título "CONTRASENA".
  - Línea de estado: "Proteccion: ACTIVADA/DESACTIVADA" y
    "Contrasena: DE FABRICA (1234) / PERSONALIZADA".
  - Sección ACTIVAR/DESACTIVAR: campo "actual" + botón toggle.
  - Sección CAMBIAR: campos "actual", "nueva", "confirmar" + botón "CAMBIAR".
  - Teclado numérico (0-9, BORRAR, LIMPIAR) como grid de rects.
  - Mensaje de resultado (éxito/error) y botón "VOLVER".
- `on_touch(screen_x, screen_y)`:
  - Tocar un campo lo selecciona (campo activo).
  - Tocar una tecla del keypad: dígito → append al campo activo (máx. razonable,
    p. ej. 16); BORRAR → quitar último; LIMPIAR → vaciar.
  - Tocar botón toggle → valida:
    - Si `target=activar` y `is_default` → `set_result("Debes cambiar la
      contraseña de fábrica (1234) antes de activar", error=True)`, sin llamar callback.
    - Si falta `current` → error "Introduce la contraseña actual".
    - Si ok → `self._on_toggle(enabled_target, current)`.
  - Tocar botón CAMBIAR → valida: `current` no vacío, `new` >= 8, `new == confirm`.
    Si ok → `self._on_change(current, new)`.
  - Tocar VOLVER → `self._on_back()`.

## Cambios en `display/app.py`

- Importar `SecuritySettingsView` desde `display.ui.widgets`.
- Añadir `"security"` a la lista de vistas (comentario + lógica).
- En `_create_widgets`: instanciar `self.security_view = SecuritySettingsView(w, h)`;
  conectar `set_on_back(_show_config)`, `set_on_toggle(_toggle_security)` y
  `set_on_change(_change_password)`.
- Añadir `_show_security()`: `self.view = "security"`, `self._redraw = True`,
  y cargar estado con `self._api_get("/api/auth/security", on_result=...)` que
  hace `security_view.set_status(data)`.
- Añadir `_toggle_security(enabled, current)` y `_change_password(current, new)`:
  encolan `_api_post_json("/api/auth/security", {"enabled": enabled, "current": current})`
  y `_api_post_json("/api/auth/password", {"current": current, "new": new})`
  respectivamente, con `on_result` que mapea el resultado a
  `security_view.set_status`/`set_result` y recarga el estado.
- Añadir ramas en `_render` (elif `self.view == "security"`) y en
  `_dispatch_touch` (elif `self.view == "security"`).
- Añadir `"security": self._show_security` al mapping de `_set_view_from_command`.
- Actualizar `ConfigOverlay.set_callbacks(...)` en `_create_widgets` con el nuevo
  callback `_show_security`.

## Tests (display)

- `display/tests/test_ui.py`: añadir test de `SecuritySettingsView`
  (keypad escribe en campo activo; validación mín. 8; bloqueo de activación con
  `is_default`; callbacks de toggle/change/back).
- `display/tests/test_display_app.py`: actualizar si hay asserts sobre el número
  de opciones del ConfigOverlay (5 → 6) o sobre las vistas.

## Verificación

- `cd display && python -m pytest -q` (o desde la raíz con `$env:PYTHONPATH=(Get-Location).Path`).
- No romper el resto: el display NO usa importaciones del backend que no existan.
- Ruff sobre los archivos tocados si aplica.

## Documentación

- `docs/ARCHITECTURE.md`: añadir la vista "security" del display físico y el
  teclado numérico; nota de limitación (solo numérico en pantalla física).

## NOTAS

- No modificar `VERSION`, `pyproject.toml`, `package.json` ni `backend/`.
- Mantener docstrings en español y el estilo existente (los widgets usan
  `pygame.Rect`, `_get_font`, `_render_text`, `_get_text_rect`, y constantes de
  `display/ui/theme.py`).
- No hacer commit ni push.
