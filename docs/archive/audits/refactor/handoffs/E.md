# Handoff E — Persistencia migrable, red no bloqueante, límites systemd y WebSocketHub

## Resultado
Completado (4/4 tareas). Sin saturación.

1. **Migraciones versionadas** en `persistence.py`: nueva tabla `schema_version`
   (`version INTEGER PRIMARY KEY`) y runner incremental (`migration_001`,
   `migration_002`). Compatibilidad con BD existente: si las tablas legacy ya
   existen y no hay versión registrada, se marca `version=1` SIN re-crearlas
   (no se pierden datos). Se conservan WAL, `aiosqlite`, conexión única,
   rotación del event log y `MAX_EVENT_LOG_ROWS=10000`. La API pública
   (`get_persistence`, `close_persistence` y métodos usados por `state_manager`)
   queda intacta; se añade `get_schema_version()` (solo lectura, aditivo).
2. **Red no bloqueante**: `network_service` sigue síncrono (sin cambios); los
   endpoints async de `api/network.py` ejecutan `get_status`/`apply_static`/
   `apply_dhcp` vía `await asyncio.to_thread(...)`. Se mantienen intactos
   `dependencies=[Depends(require_admin_api_key)]` y la semántica de B.
3. **systemd**: añadidos `MemoryMax=256M`, `CPUQuota=100%`, `TasksMax=256`,
   `LimitNOFILE=65536`, `UMask=0077` (documentados con comentarios). Se mantiene
   `User=pi`, `Restart=on-failure` y todo el hardening previo. **Watchdog NO
   activado**: queda documentado como mejora futura (no se añade `WatchdogSec=`
   sin notificador `sd_notify`).
4. **Split StateManager → WebSocketHub**: nuevo `ws_hub.py` con la clase
   `WebSocketHub` que encapsula `_subscribers`, `_sequence`, `_broadcast_queues`
   y `_broadcast_workers`. `StateManager` DELEGA en el hub manteniendo su API
   pública (`subscribe`, `unsubscribe`, `broadcast`, `_next_sequence`, etc.),
   por lo que `hmi.py`/`ws.py` **no cambiaron**.

Suite verde: pytest **220 passed, 2 skipped**, mypy **0 errores (25 ficheros)**,
smoke import `from backend.app.services.state_manager import state_manager` → `ok`.

## Archivos modificados
- [editado] `backend/app/services/persistence.py` — tabla `schema_version`,
  runner de migraciones (`_MIGRATIONS`, `_migration_001`, `_migration_002`),
  `_has_legacy_tables`, `_get_schema_version`, `get_schema_version`. Resto igual.
- [nuevo] `backend/app/services/ws_hub.py` — clase `WebSocketHub`.
- [editado] `backend/app/services/state_manager.py` — instancia `WebSocketHub`
  (lock compartido), secuencia/suscripciones/broadcast delegados; `_sequence`
  pasa a property de solo lectura (compat con tests).
- [editado] `backend/app/api/network.py` — endpoints async con `asyncio.to_thread`
  (import de `asyncio`). Caller autorizado ("solo si es imprescindible"): aquí
  es imprescindible para la tarea 2.
- [editado] `config/systemd/rpi-hmi-backend.service` — límites de recursos +
  bloque de comentario "Watchdog (mejora futura, no activar)".

No tocados: `backend/app/api/hmi.py`, `backend/app/api/ws.py`,
`backend/app/main.py`, `backend/app/services/network_service.py`.

## Verificación ejecutada
- `python -m pytest backend/tests/ -q` (raíz del repo) → **220 passed, 2 skipped** (1 warning preexistente en `test_restore_from_db_sets_led_and_button`).
- `cd backend && python -m mypy app/ --config-file pyproject.toml` → **Success: no issues found in 25 source files**.
- `python -c "from backend.app.services.state_manager import state_manager; print('ok')"` → `ok`.
- Smoke de migraciones (manual): BD legacy → `schema_version=2`, datos preservados
  (led=True, button=42); BD nueva → `schema_version=2`. OK.
- `ReadLints` sobre `persistence.py`, `ws_hub.py`, `state_manager.py`, `network.py` → sin errores.

## Decisiones tomadas
1. **`schema_version` con `version INTEGER PRIMARY KEY` y `MAX(version)`** como
   lectura actual: simple, idempotente (`INSERT OR REPLACE`) y sin dependencias
   externas.
2. **`migration_001` = esquema original** (`CREATE TABLE IF NOT EXISTS` +
   `INSERT OR IGNORE`), **`migration_002` = índice `idx_event_log_timestamp`**
   (aditivo e inofensivo) para demostrar el patrón incremental.
3. **Detección de BD existente**: `_has_legacy_tables()` (busca `led_state` en
   `sqlite_master`) + `schema_version` vacía ⇒ `INSERT OR IGNORE version=1`.
   Así la migración 001 no se re-ejecuta sobre datos ya existentes (aunque es
   idempotente). BD nueva ⇒ 001 crea todo y registra 1, luego 002.
4. **`WebSocketHub` comparte el `threading.Lock` de `StateManager`** (inyectado
   por constructor) para no introducir un segundo lock que compita con
   `get_status`/mutaciones. `next_sequence()` no adquiere el lock: debe llamarse
   mientras el llamador ya lo mantiene (evita deadlock con `threading.Lock` no
   reentrante).
5. **`_sequence` como property de solo lectura en `StateManager`** (delega a
   `hub.sequence`): preserva el contrato implícito del test
   `test_concurrent_toggle_consistent_state` (`sm._sequence >= 100`) sin exponer
   mutación externa. El alias `_schedule_broadcast` se conserva delegando al hub.
6. **`get_status` usa `self._hub.subscribers`**: `ws_count` sigue contando
   clientes únicos idéntico a antes.
7. **systemd**: valores conservadores para una Pi de 1 GB / 1 núcleo.
   `UMask=0077` (dirs 0700, ficheros 0600). Watchdog documentado pero NO activado.

## Riesgos / pendientes
- **`asyncio.to_thread`**: no hay tests unitarios que ejerzan los endpoints de
  red; el cambio está validado por la suite (que sigue verde) y por inspección.
  En producción, `nmcli` sigue necesitando la regla sudoers de B.
- **`MemoryMax=256M`** es una estimación razonable; si el backend crece
  (features, mayor concurrencia WS) puede requerir subirlo. No bloqueante.
- **Watchdog pendiente**: implementar `sdnotify` (READY=1 + WATCHDOG=1) y entonces
  añadir `WatchdogSec=` + `Type=notify`. No activar antes.
- El `RuntimeWarning` de pytest en `test_restore_from_db_sets_led_and_button` es
  preexistente (no introducido aquí).
- Las migraciones no llevan test unitario dedicado en el repo; se validaron con
  smoke manual (BD legacy y BD nueva). Podría añadirse en el futuro.

## Texto de paso al siguiente agente
Workstream E completo y en verde. No queda trabajo pendiente dentro del alcance.

Para el orquestador / siguientes agentes:
- No revertir el delegado `WebSocketHub` ni el `_sequence` como property.
- Para activar watchdog (trabajo futuro): añadir notificador `sdnotify` en el
  backend, cambiar `Type=simple`→`Type=notify`, y recién entonces añadir
  `WatchdogSec=30s` (borrando el bloque de comentario en
  `config/systemd/rpi-hmi-backend.service`).
- Los límites systemd deben validarse en la Pi real (`systemd-analyze verify`
  y `systemctl daemon-reload`).
