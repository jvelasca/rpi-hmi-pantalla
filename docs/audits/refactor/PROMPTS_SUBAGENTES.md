# Prompts de Subagentes (autocontenidos)

> Cada prompt es **autocontenido**: el subagente no tiene acceso al historial del chat principal,
> así que aquí va TODO lo que necesita (contexto, archivos, criterio de done, handoff).

---

## A1 — Display tests + feedback no-bloqueante del botón

**Contexto.** El proyecto es un HMI de Raspberry Pi (backend FastAPI + display Pygame + frontend SolidJS).
La suite `pytest display/tests/` está en rojo con 16 fallos. 15 son "drift" (los tests usan
`Clase.__new__()` para saltarse `pygame.init()` y no inicializan atributos que el código añadió en el
refactor de vistas V1.1–V1.3). 1 es un bug real de funcionalidad (feedback del botón).

**Archivos que posees en exclusiva:** `display/tests/**` y `display/app.py`. NO toques nada más.

**Tareas:**
1. Corrige los 15 fallos de drift. Los tests afectados instancian con `__new__` y les faltan atributos:
   - `TestTouchCoordinateMapping` (6): `TouchHandler.__new__` no fija los coeficientes afines
     `_a_xx, _a_xy, _a_yx, _a_yy, _b_x, _b_y`. Debes inicializarlos en el test con los mismos valores
     que `__init__` usa por defecto (rotate=270), respetando `screen_width/height/touch_max_x/y`.
   - `_apply_ws_state` (5 tests en `test_display_app.py` y `test_ui.py`): falta `_pending_display_action`,
     `_pending_font_family`, `_pending_text_size`.
   - `_handle_touch_down` (4 tests): falta `self.view = "main"`.
   - Decide caso a caso si es más limpio inicializar el atributo en el test o refactorizar el código para
     ser defensivo. No cambies el comportamiento del código de producción salvo donde el fallo lo exija.
2. Implementa el **feedback no-bloqueante del botón** (bug real) en `display/app.py`:
   - Añade `self._button_press_frame = -1` y `self._button_press_duration = 2` en `__init__`.
   - En `_on_press_button`, fija `self._button_press_frame = 0`.
   - En el bucle principal de `run()`, incrementa el contador por frame y, si alcanza la duración,
     auto-libera el botón (llama a `_on_release_button`) si aún sigue presionado.
   - El feedback debe ser visual (estado `pressed`) sin bloquear el bucle.
3. Verifica: `python -m pytest display/tests/ -q` debe quedar **verde** (0 fallos).

**Definición de done:** `pytest display/tests/` = 0 fail. Escribe el handoff.

**Handoff obligatorio:** escribe `docs/audits/refactor/handoffs/A1.md` siguiendo la plantilla de
`docs/audits/refactor/handoffs/_PLANTILLA.md`. Incluye archivos modificados, verificación ejecutada,
decisiones y "texto de paso".

**Saturación:** si te quedas sin contexto, escribe el handoff con estado parcial y un "texto de paso"
que diga exactamente desde dónde continuar. Devuelve un resumen corto. NUNCA digas "hecho" sin handoff.

---

## A2 — mypy strict a cero

**Contexto.** `python -m mypy app/ --config-file pyproject.toml` (desde `backend/`) da **57 errores**.
Causa principal: `[tool.mypy]` tiene `strict = true` pero **falta** `plugins = ["pydantic.mypy"]`, por lo
que los defaults declarados con `Annotated[..., Field(default=...)]` no se reconocen y genera decenas de
`Missing named argument` falsos en `state_manager.py` y `ws.py`.

**Archivos que posees en exclusiva:** `backend/pyproject.toml` y `backend/app/**` (solo cambios de
anotaciones de tipo; NO cambies lógica de negocio ni comportamiento).

**Tareas:**
1. Añade `plugins = ["pydantic.mypy"]` a `[tool.mypy]` en `backend/pyproject.toml` y verifica que el
   plugin `pydantic` esté disponible en el entorno (si no, instálalo o añádelo a `[project.optional-dependencies].dev`).
2. Corrige las violaciones strict **reales** (no relacionadas con pydantic), entre ellas:
   - `state_manager.py`: `asyncio.Task` sin parámetros → `Task[Any]`; `Queue` → `Queue[Any]`;
     `dict` → `dict[str, ...]`; función sin anotación (línea 517).
   - `network_service.py:170`: `mode: str` vs `Literal['dhcp','static']`.
   - `state_manager.py:387-388`: `font_family`/`text_size: str` vs `Literal[...]`.
   - `gpio_service.py:31`: stubs de `yaml` → añade `types-PyYAML` a deps de dev o un `# type: ignore[import-untyped]` justificado.
3. NO elimines la rigurosidad: mantén `strict = true`. Usa `# type: ignore` solo con código de error y justificación.

**Definición de done:** `cd backend && python -m mypy app/ --config-file pyproject.toml` = **0 errores**,
y `pytest backend/tests/` sigue verde (no debe romper nada).

**Handoff obligatorio:** escribe `docs/audits/refactor/handoffs/A2.md` (plantilla en `handoffs/_PLANTILLA.md`).

**Saturación:** igual que A1: checkpoint parcial + "texto de paso".

---

## B — Seguridad de red + README + sudoers

**Contexto.** La auditoría externa encontró que `POST /api/network/static` y `POST /api/network/dhcp`
son **públicos** (sin API key), mientras que `/admin/*` sí está protegido. El servidor escucha en
`0.0.0.0:8000`, así que cualquiera en la LAN puede cambiar la IP y dejar la Pi inaccesible. Además:
`README.md` dice que el LED está en GPIO17 (falso: es virtual; GPIO17 es la IRQ del touch), y
`NetworkService` ejecuta `sudo nmcli` desde un servicio `User=pi` sin que exista una regla sudoers documentada.

**Archivos que posees en exclusiva:** `backend/app/api/network.py`, `backend/app/api/deps.py` (NUEVO),
`backend/app/config.py`, `backend/app/main.py`, `README.md` (solo secciones GPIO17/red), `config/sudoers.d/rpi-hmi` (NUEVO).

**Decisiones ya tomadas (NO las reviertas):**
- Modelo de seguridad configurable: `SECURITY_MODE=local|protected`. En `local` (default), HMI sin auth
  (prototipo doméstico). En `protected`, endpoints que mutan hardware/red exigen API key.
- `/api/network/*` pasa a requerir auth en modo `protected` (o se mueve a `/admin/network/*`). Elige la
  opción más simple y consistente con el `ENABLE_ADMIN_API` ya existente; documenta la elección.

**Tareas:**
1. Implementa el gating de `/api/network/*`: dependencia de autenticación reutilizable en `deps.py`
   (`require_admin_api_key` o `require_protected`) usando `secrets.compare_digest` (como ya hace `/admin/*`).
2. Añade `SECURITY_MODE` a `config.py` con validación en `model_post_init` y `env` configurable.
3. Corrige `README.md`: LED es **virtual** (`devices.yaml`), NO GPIO17; GPIO17 = IRQ del touch.
4. Crea `config/sudoers.d/rpi-hmi` con regla mínima `pi → /usr/bin/nmcli` (NO `ALL`), y documenta su
   instalación en el README o en el handoff.
5. Verifica: `pytest backend/tests/` verde + `mypy` verde (no empeorar A2).

**Definición de done:** endpoint de red protegido en `protected`, README corregido, sudoers creado y documentado, tests verdes.

**Handoff obligatorio:** `docs/audits/refactor/handoffs/B.md`.

---

## C — Display DRM hardening

**Contexto.** En `display/ui/screen.py`, `Screen.init()` hace fallback silencioso DRM→mock:
```python
except Exception:
    if not self.mock:
        self.mock = True
        return self.init()
```
En producción, si el TFT falla, el servicio systemd queda "vivo" en mock con la pantalla física apagada.
Además, `_detect_display()` solo comprueba la existencia de `/dev/dri/card0`, no si el conector está
realmente conectado/activo.

**Archivos que posees en exclusiva:** `display/ui/screen.py`, `config/systemd/rpi-hmi-display.service`.

**Tareas:**
1. Separa el fallback: en **producción** (sin `--mock`), si DRM falla → devolver `False` (o lanzar) para
   que `DisplayApp.run()` devuelva `exit 1` y systemd reinicie. En **desarrollo** (`--mock` explícito),
   mantener el modo mock.
2. Mejora `_detect_display()` para comprobar el estado real del conector DRM (status/modes/EDID) cuando sea
   posible, con fallback seguro a los drivers fb1/mock.
3. Ajusta `config/systemd/rpi-hmi-display.service` si es necesario (p. ej. `Restart=on-failure` ya existente,
   `RestartSec`, o env vars).
4. Verifica: `pytest display/tests/` sigue verde (A1) y el smoke de importación de `screen.py`.

**Definición de done:** DRM falla → exit 1 (no mock silencioso) en producción; detección de conector mejorada.

**Handoff obligatorio:** `docs/audits/refactor/handoffs/C.md`.

---

## D — Frontend hardening (WS + resync + IP fija)

**Contexto.** En `frontend/src/hooks/useWebSocket.ts`, la "validación runtime" es en realidad un cast:
`return raw as unknown as ServerMessage;`. Además hay un bug de sequence/resync: se hace
`lastSequence = raw.sequence` **antes** de que termine el resync, pudiendo mezclar eventos WS con el
snapshot REST. Y `frontend/vite.config.ts` tiene hardcodeada la IP `192.168.88.211:8000`.

**Archivos que posees en exclusiva:** `frontend/src/**`, `frontend/vite.config.ts`, `frontend/package.json`.

**Decisiones ya tomadas:**
- Usar **Zod** para validación runtime (añadir `zod` a `package.json`). Esquema en `frontend/src/schemas/ws.ts`.
- Máquina de estados `NORMAL → RESYNCING → NORMAL` en `useWebSocket`: al detectar gap, entrar en RESYNCING
  y **descartar** eventos hasta que el snapshot de `/api/status` complete; luego volver a NORMAL.
- Eliminar IP fija: usar `VITE_API_URL` (con default) y proxy configurable.

**Tareas:**
1. Añadir Zod + esquemas de `ServerMessage`/`ClientMessage` y reemplazar `validateMessage` (cast) por `parse`.
2. Corregir el flujo sequence/resync con estado RESYNCING.
3. Quitar `192.168.88.211` de `vite.config.ts` → `VITE_API_URL` / env.
4. Asegurar que `ServerMessage` TS incluya `sequence` en TODAS las variantes (incluida `error`).
5. Verifica: `cd frontend && npm run test` verde (16/16) + `npm run build` verde.

**Definición de done:** validación Zod real, resync con estado, sin IP fija, tests+build verdes.

**Handoff obligatorio:** `docs/audits/refactor/handoffs/D.md`.

---

## E — Arquitectura (StateManager / persistencia / red / watchdog)

**Contexto.** `StateManager` acumula demasiadas responsabilidades (DeviceState + EventBus + Persistence +
WebSocketHub + comandos de display). `NetworkService` usa `subprocess.run` bloqueante dentro de endpoints
`async`. `persistence.py` usa `CREATE TABLE IF NOT EXISTS` sin versionado de esquema. Falta watchdog y
límites de recursos en systemd.

**Archivos que posees en exclusiva:** `backend/app/services/state_manager.py`,
`backend/app/services/persistence.py`, `backend/app/services/network_service.py`,
`config/systemd/rpi-hmi-backend.service`.

**Tareas (secuencial, con resume si satura):**
1. Extraer de `StateManager` un `WebSocketHub` (suscribers/sequence/broadcast) y, opcionalmente, un
   `EventBus`, manteniendo la API pública que ya consumen `hmi.py`/`ws.py` (o actualizando esos callers
   si es imprescindible; en ese caso coordina el cambio para no romper `backend/tests`).
2. Mover `subprocess.run` de `network_service` a `asyncio.to_thread` (endpoint async no bloqueante).
3. Añadir versionado de esquema + migraciones simples a `persistence.py` (tabla `schema_version`).
4. Añadir `WatchdogSec`/límites (`MemoryMax`, `CPUQuota`, `TasksMax`, `UMask`) a
   `config/systemd/rpi-hmi-backend.service`.
5. Verifica tras cada sub-tarea: `pytest backend/tests/` + `mypy` verdes.

**Definición de done:** StateManager desacoplado, red no bloqueante, schema versionado, systemd con límites, suite verde.

**Handoff obligatorio:** `docs/audits/refactor/handoffs/E.md`. Si saturas, checkpoint parcial + "texto de paso".

---

## F — Docs/consistencia (SECURITY.md, versiones, safe-state)

**Contexto.** Falta un `docs/SECURITY.md` con el modelo de amenazas (PUBLIC/LOCAL/ADMIN) y documentar que
`/admin/ssh/execute` es superficie RCE. Las versiones visibles están descoordinadas (`display/app.py`
muestra "v1.2"/"v0.1" vs `VERSION` 0.3.0). El README tiene conteos de tests incoherentes (~180/222/277).

**Archivos que posees en exclusiva:** `docs/**` (incluido `docs/SECURITY.md` NUEVO), `VERSION`,
`README.md` (solo conteo de tests), cadenas de versión en `display/app.py`.

**Nota de secuencia:** ejecútate **después** de A1 y B (compartes `display/app.py` y `README.md`).

**Tareas:**
1. Crear `docs/SECURITY.md`: modelo de amenazas, política PUBLIC/LOCAL/ADMIN, documentar RCE en
   `/admin/ssh/execute`, y los estados de fallo/safe-state por dispositivo (startup/failure/shutdown).
2. Unificar versiones visibles a `0.3.0` (leer de `VERSION` si es factible, o fijar cadenas consistentes).
3. Limpiar el conteo de tests del README: un único número real, obtenido de la suite ejecutada.
4. Verifica que no rompes nada (docs/version no afectan tests; revisa imports de `display/app.py`).

**Definición de done:** SECURITY.md creado, versiones coherentes, README con un único conteo real.

**Handoff obligatorio:** `docs/audits/refactor/handoffs/F.md`.
