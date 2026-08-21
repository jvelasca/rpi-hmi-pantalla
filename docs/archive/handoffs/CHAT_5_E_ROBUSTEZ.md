# HANDOFF — Chat 5: Fase E — Robustez y Refinamiento Final

> **Precondición:** Chats 1, 2, 3 y 4 completados
> **Salida esperada:** `docs/handoffs/CHAT_5_E_RESULTADO.md` (documento de cierre)
> **Duración estimada:** 60-90 min

---

## Contexto

Esta es la última fase. El backend está sólido, el deploy funciona, la concurrencia está
corregida y la seguridad está hardened. Ahora refinamos detalles de robustez que mejoran
la calidad general sin cambiar la arquitectura.

---

## TAREA 1: Display — eliminar polling REST redundante cuando WS está conectado

**Archivo:** `display/app.py`

Actualmente el display hace polling REST cada 500ms incluso cuando el WebSocket está
conectado y recibiendo actualizaciones en tiempo real:

```101:101:display/app.py
        self._sync_interval: float = 0.5  # 500ms entre polls REST
```

Y en el bucle principal (líneas 401-409):

```401:409:display/app.py
            # ── Sincronizacion periodica con backend ──
            now = time.time()
            if now - self._last_sync > self._sync_interval:
                old_led = self.led_on
                old_count = self.press_count
                self._sync_state()
                if old_led != self.led_on or old_count != self.press_count:
                    dirty = True
                self._last_sync = now
```

**Cambios:**

1. Cambiar `_sync_interval` por defecto a 3.0 (3 segundos en lugar de 500ms):

```python
        self._sync_interval: float = 3.0  # 3s entre polls REST (fallback cuando WS cae)
```

2. Modificar la condición de sincronización para que solo haga polling REST cuando el
   WebSocket NO está conectado:

```python
            # ── Sincronizacion periodica con backend (solo si WS no conectado) ──
            now = time.time()
            with self._ws_lock:
                ws_ok = self.ws_connected
            if not ws_ok and now - self._last_sync > self._sync_interval:
                old_led = self.led_on
                old_count = self.press_count
                self._sync_state()
                if old_led != self.led_on or old_count != self.press_count:
                    dirty = True
                self._last_sync = now
```

---

## TAREA 2: Touch — eliminar fallback ciego `candidates[0]`

**Archivo:** `display/ui/touch.py`

Línea 62 de `_find_touch_device()`:

```60:62:display/ui/touch.py
    # Fallback
    if Path(preferred).exists():
        return preferred
    return candidates[0] if candidates else None
```

El problema: si no encuentra un dispositivo touch por nombre, coge el primer `event*`
que exista, que podría ser un teclado, ratón, o cualquier otra cosa.

**Cambiar a:**

```python
    # Fallback: solo usar preferred si existe, NUNCA elegir arbitrariamente
    if Path(preferred).exists():
        logger.info("Usando dispositivo preferido: %s", preferred)
        return preferred
    logger.warning("No se encontro dispositivo tactil. Touch deshabilitado.")
    return None
```

---

## TAREA 3: Touch — obtener capacidades desde evdev en lugar de RAW_MAX hardcodeado

**Archivo:** `display/ui/touch.py`

Actualmente `RAW_MAX = 4096` está hardcodeado (línea 28). Para el XPT2046 funciona, pero
no es robusto. Añadir un método que lea `ABS_X`, `ABS_Y` y `ABS_PRESSURE` min/max desde
el dispositivo evdev.

Añadir este método a la clase `TouchHandler` (después de `_init_device`, antes de `poll`):

```python
    def _read_capabilities(self) -> None:
        """Lee las capacidades reales del dispositivo evdev.

        Obtiene ABS_X, ABS_Y y ABS_PRESSURE min/max desde el driver,
        en lugar de usar RAW_MAX hardcodeado.
        """
        if self._fd is None or self.device_path is None:
            return

        try:
            import struct as _struct
            import fcntl as _fcntl
            import array as _array

            # ioctls de evdev para leer abs info
            EVIOCGABS = lambda axis: (0x80000000 | 0x40 | (0x40 + axis)) << 0

            for axis, attr in [(ABS_X, "touch_max_x"), (ABS_Y, "touch_max_y"), (ABS_PRESSURE, "touch_max_pressure")]:
                try:
                    # struct input_absinfo: value, minimum, maximum, fuzz, flat, resolution
                    abs_info = _array.array("i", [0] * 6)
                    buf = abs_info.tobytes()
                    result = _fcntl.ioctl(self._fd, EVIOCGABS(axis), buf)
                    values = _struct.unpack("iiiiii", result)
                    max_val = values[2]
                    if max_val > 0:
                        # Guardar max; pressure usa su propio atributo
                        if attr == "touch_max_pressure":
                            setattr(self, attr, max_val)
                        else:
                            setattr(self, attr, max_val)
                        logger.info("Touch cap: %s max=%d", attr, max_val)
                except (OSError, IOError):
                    pass  # El eje no existe en este dispositivo

        except Exception as exc:
            logger.debug("No se pudieron leer capacidades evdev: %s", exc)
            # Mantener defaults (RAW_MAX)
```

Y añadir el atributo en `__init__`:

```python
        self.touch_max_pressure: int = 4096  # Max pressure (se actualiza con _read_capabilities)
```

Y llamar a `self._read_capabilities()` al final de `_init_device()`:

```python
    def _init_device(self, device_path: str | None) -> None:
        """Abre el dispositivo táctil en modo no bloqueante."""
        path = device_path or _find_touch_device()
        if path is None:
            logger.warning("Dispositivo táctil no encontrado")
            return

        try:
            flags = os.O_RDONLY
            if hasattr(os, "O_NONBLOCK"):
                flags |= os.O_NONBLOCK
            fd = os.open(path, flags)
            self._fd = fd
            self.device_path = path
            logger.info("Touch inicializado en %s", path)
            self._read_capabilities()  # <-- AÑADIR ESTA LÍNEA
        except OSError as exc:
            logger.warning("No se pudo abrir %s: %s", path, exc)
```

---

## TAREA 4: Separar `backend/requirements.txt`

**Archivo:** `backend/requirements.txt`

Actualmente mezcla runtime + display + deploy + dev. Separar en secciones claras:

```txt
# ============================================================
# RPi HMI Backend — Dependencias
# ============================================================
# Instalacion:
#   pip install -r requirements.txt                  (runtime)
#   pip install -r requirements.txt dev              (dev tools)
#   pip install -r requirements.txt display           (display + touch)
# ============================================================

# === Runtime (FastAPI + GPIO + SQLite) ===
fastapi>=0.115.0
uvicorn[standard]>=0.30.0
pydantic>=2.5.0
pydantic-settings>=2.1.0
websockets>=12.0
gpiozero>=2.0
pyyaml>=6.0
python-dotenv>=1.0
aiosqlite>=0.20.0

# === Deploy (solo PC de desarrollo) ===
paramiko>=3.4

# === Display (solo en Raspberry Pi con TFT) ===
# pygame>=2.6
# evdev>=1.7

# === Dev & Testing (solo desarrollo) ===
# pytest>=8.0
# pytest-asyncio>=0.24
# pytest-cov>=4.1
# httpx>=0.27
# mypy>=1.14
# ruff>=0.8
```

---

## TAREA 5: Vaciar `backend/__init__.py` y `backend/app/__init__.py`

### 5a. `backend/__init__.py`

```1:12:backend/__init__.py
"""Backend FastAPI para RPi HMI — Panel de control industrial.

Paquete principal que expone la aplicacion FastAPI lista para
ser servida por uvicorn.

Uso:
    uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
"""

from backend.app.main import app

__all__ = ["app"]
```

**Cambiar a:**

```python
"""Backend package for RPi HMI."""
```

### 5b. `backend/app/__init__.py`

```1:8:backend/app/__init__.py
"""Paquete `backend.app` — nucleo de la aplicacion FastAPI.

Expone la instancia `app` lista para ser servida por uvicorn.
"""

from backend.app.main import app

__all__ = ["app"]
```

**Cambiar a:**

```python
"""Application package for RPi HMI."""
```

> **IMPORTANTE:** Verificar que `uvicorn backend.app.main:app` sigue funcionando después
> de este cambio. La app se importa explícitamente en `main.py`, no a través de `__init__.py`.
> El systemd service usa `uvicorn backend.app.main:app` que no depende de `__init__.py`.

---

## TAREA 6: Frontend — añadir validación runtime de mensajes WebSocket

**Archivo:** `frontend/src/hooks/useWebSocket.ts`

Línea 40 actualmente hace un cast sin validación:

```40:41:frontend/src/hooks/useWebSocket.ts
        const msg = JSON.parse(event.data) as ServerMessage;
        onMessage(msg);
```

**Cambiar a** (validación básica sin dependencia externa):

```typescript
      try {
        const raw = JSON.parse(event.data);
        // Validación runtime básica: el mensaje debe tener type y data
        if (typeof raw !== "object" || raw === null || typeof raw.type !== "string") {
          console.warn("WS: mensaje inválido (sin type)", raw);
          return;
        }
        const msg = raw as ServerMessage;
        onMessage(msg);
      } catch {
        // Ignore malformed messages
      }
```

---

## TAREA 7: Frontend — `gpio_pin: 0` como estado inicial

**Archivo:** `frontend/src/App.tsx`

Línea 19:

```19:19:frontend/src/App.tsx
    gpio_pin: 17,
```

**Cambiar a:**

```typescript
    gpio_pin: 0,  // Se sincroniza con backend en la primera respuesta
```

También actualizar los tests que esperan `gpio_pin: 17`. Buscar en `frontend/src/tests/`:

**Archivo:** `frontend/src/tests/hooks.test.tsx`

Cambiar todas las ocurrencias de `gpio_pin: 17` a `gpio_pin: 0` en los datos de test
(líneas 23, 66, 164, 190, 220, 224, 238). Los tests deben reflejar el nuevo valor inicial.

---

## TAREA 8: Display WebSocket — añadir `version` al subscribe

**Archivo:** `display/app.py`

Línea 267:

```267:267:display/app.py
            ws.send(json.dumps({"type": "subscribe", "topics": ["led", "button"]}))
```

**Cambiar a:**

```python
            ws.send(json.dumps({
                "type": "subscribe",
                "topics": ["led", "button"],
                "version": "1.0",
            }))
```

---

## TAREA 9: Health — simplificar `_check_db()` duplicado

**Archivo:** `backend/app/api/health.py`

Hay dos funciones que verifican la BD: `_check_db()` (síncrona, no hace SELECT 1 real)
y `_check_db_async()` (asíncrona, sí hace SELECT 1). `_check_db()` se llama en
`_collect_checks_sync()` y luego se reemplaza por `_check_db_async()` en
`_collect_checks_async()`.

**Cambio:** Eliminar `_check_db()` de `_collect_checks_sync()` para evitar el check
innecesario:

```209:227:backend/app/api/health.py
def _collect_checks_sync() -> dict[str, HealthCheckDetail]:
    """Ejecuta todos los checks sincronos y devuelve el diccionario."""
    checks: dict[str, HealthCheckDetail] = {}

    for name, func in [
        ("api", _check_api),
        ("uptime", _check_uptime),
        ("gpio", _check_gpio),
        ("display", _check_display),
        ("db", _check_db),
        ("cpu", _check_cpu),
        ("ws", _check_ws),
    ]:
        try:
            checks[name] = func()
        except Exception:
            checks[name] = HealthCheckDetail(status="fail", message=f"Error al verificar {name}")

    return checks
```

**Cambiar a** (eliminar `("db", _check_db)` de la lista):

```python
def _collect_checks_sync() -> dict[str, HealthCheckDetail]:
    """Ejecuta todos los checks sincronos y devuelve el diccionario."""
    checks: dict[str, HealthCheckDetail] = {}

    for name, func in [
        ("api", _check_api),
        ("uptime", _check_uptime),
        ("gpio", _check_gpio),
        ("display", _check_display),
        # ("db", ...) se añade async en _collect_checks_async
        ("cpu", _check_cpu),
        ("ws", _check_ws),
    ]:
        try:
            checks[name] = func()
        except Exception:
            checks[name] = HealthCheckDetail(status="fail", message=f"Error al verificar {name}")

    return checks
```

La función `_check_db()` puede mantenerse (no borrarla) porque podría usarse en otros
contextos, pero ya no se llamará en el flujo normal.

---

## VERIFICACIÓN FINAL

```bash
# === Compilación de todos los módulos Python ===
python -m py_compile backend/app/services/state_manager.py
python -m py_compile backend/app/services/deploy_service.py
python -m py_compile backend/app/config.py
python -m py_compile backend/app/main.py
python -m py_compile backend/app/api/health.py
python -m py_compile display/app.py
python -m py_compile display/ui/touch.py

# === Versión unificada ===
cat VERSION                                    # 0.3.0
grep '"version"' backend/pyproject.toml        # 0.3.0
grep 'version=' backend/app/main.py            # 0.3.0 (2 ocurrencias)
grep '"version"' frontend/package.json         # 0.3.0

# === Limpieza ===
find . -name "*.pyc" -o -type d -name "__pycache__" | wc -l  # 0
ls frontend/Untitled 2>&1 | grep "No such"                   # Confirmado eliminado

# === Deploy ===
grep "restart_backend" scripts/deploy.py       # Aparece en flujo default
grep "ensure_backend" scripts/deploy.py        # Solo en definición, no en flujo

# === DeployService ===
grep "frontend" backend/app/services/deploy_service.py  # En DEPLOY_DIRECTORIES y allowed_extensions

# === Concurrencia ===
grep -A 3 "self._sequence += 1" backend/app/services/state_manager.py  # 4 ocurrencias
grep "seq = self._sequence" backend/app/services/state_manager.py      # 4 ocurrencias, dentro de locks

# === Seguridad ===
grep "enable_admin_api" backend/app/config.py  # Campo + validación
grep "enable_admin_api" backend/app/main.py    # Condición para admin routers

# === Robustez ===
grep "ws_ok" display/app.py                    # Polling condicionado a WS
grep "candidates\[0\]" display/ui/touch.py     # YA NO DEBE EXISTIR
grep "from backend.app.main import app" backend/__init__.py    # YA NO DEBE EXISTIR
grep "runtime validation" frontend/src/hooks/useWebSocket.ts   # Comentario presente
grep '"version": "1.0"' display/app.py                          # En subscribe WS

# === Tests ===
python -m pytest backend/tests/test_state_manager.py -v --tb=short
```

---

## AL FINALIZAR

Crea `docs/handoffs/CHAT_5_E_RESULTADO.md` con:

1. Resumen de TODOS los cambios realizados en las 5 fases
2. Resultado de la verificación final
3. Checklist de verificación completada
4. Incidencias o cosas pendientes para el futuro

Este es el documento de **cierre del plan de consolidación**. No hay handoff a otro chat.

Incluye al final este resumen:

```
=== PLAN DE CONSOLIDACIÓN COMPLETADO ===

5 fases ejecutadas:
- Fase A: Limpieza y unificación de versión (0.3.0)
- Fase B: Corrección del flujo de deploy
- Fase C: Bugs de concurrencia WebSocket
- Fase D: Hardening de seguridad
- Fase E: Robustez y refinamiento

Versión final: 0.3.0
Estado: Release candidate
```
