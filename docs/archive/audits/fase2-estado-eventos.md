# FASE 2 — Estado y eventos ✅ COMPLETADA

**Fecha:** 2026-08-11
**Tests:** 81/81 pasando
**Resultado:** ws_count corregido a clientes únicos, uptime_seconds corrige offset desde arranque, protocolo WS versionado

---

## Cambios realizados

### 1. 🔴 `ws_count` — clientes únicos (no subscribers por topic)

| Antes | Ahora |
|-------|-------|
| `sum(len(v) for v in self._subscribers.values())` — mismo cliente contado N veces | `len({ws for subs in self._subscribers.values() for ws in subs})` — set comprehension de clientes únicos |

**Archivo:** `backend/app/services/state_manager.py` línea 196

- Si un cliente está suscrito a 3 topics, antes contaba 3. Ahora cuenta 1.
- Los nuevos tests validan: 2 clientes en 3 topics → `websocket_clients = 2`, y 0 sin clientes.

### 2. 🔴 `uptime_seconds` — tiempo desde arranque del servicio

| Antes | Ahora |
|-------|-------|
| `time.monotonic()` en `from_manager()` — devolvía tiempo desde boot del SO | `time.monotonic() - self._start_time` calculado en `StateManager.get_status()` y pasado como parámetro explícito |

**Archivos:** `backend/app/services/state_manager.py` + `backend/app/models/hmi.py`

- `StateManager.__init__()` guarda `self._start_time = time.monotonic()`
- `get_status()` calcula `uptime = time.monotonic() - self._start_time` bajo el lock
- `SystemStatus.from_manager()` ahora recibe `uptime_seconds: float` como parámetro
- Eliminado `import time` de `hmi.py` (ya no se usa)

### 3. 🟡 Versionado del protocolo WebSocket

| Antes | Ahora |
|-------|-------|
| Sin campo `version` en mensajes | `version: str = "1.0"` en `ClientMessage` y `ServerMessage` |

**Archivos:** `backend/app/models/events.py` + `frontend/src/types/api.ts`

- `ClientMessage` y `ServerMessage` tienen `version` con default `"1.0"`
- Tipos TypeScript en frontend sincronizados con `version: string`
- **Retrocompatible:** clientes existentes que no envíen `version` funcionan (Pydantic auto-fill del default)

---

## Archivos modificados (5)

| Archivo | Tipo de cambio |
|---------|---------------|
| `backend/app/services/state_manager.py` | +`_start_time`, +`import time`, `get_status` recalcula ws_count y uptime |
| `backend/app/models/hmi.py` | `from_manager` acepta `uptime_seconds` explícito, elimina `import time` |
| `backend/app/models/events.py` | +campo `version` en `ClientMessage` y `ServerMessage` |
| `frontend/src/types/api.ts` | +campo `version: string` en todos los tipos de mensajes WS |
| `backend/tests/test_state_manager.py` | +4 tests: ws_count único, ws_count cero, uptime inicial, uptime crece |

---

## Nuevos tests (4)

| Test | Qué valida |
|------|-----------|
| `test_ws_count_counts_unique_clients` | 2 clientes suscritos a 3 topics → `websocket_clients = 2` |
| `test_ws_count_zero_with_no_clients` | Sin clientes → `websocket_clients = 0` |
| `test_uptime_starts_at_zero_or_near` | Uptime ≥ 0 y < 5s justo tras init |
| `test_uptime_increases_over_time` | `time.sleep(0.1)` → uptime crece |

---

## Verificación

- `python -m pytest backend/tests/ -v --tb=short` → **81 passed**
- Sin linter errors en los 5 archivos modificados
- `display/app.py` no modificado: su cliente WS sigue funcionando (Pydantic auto-fill del `version` default)

---

## Próxima fase: FASE 3 — Display

**Prompt para el siguiente chat:**

> Continuamos el plan de trabajo consolidado para el proyecto Rpi_Pantalla_V1 (Raspberry Pi HMI).
>
> Las FASE 0 (Seguridad), FASE 1 (Arquitectura) y FASE 2 (Estado/eventos) están completadas — 81/81 tests pasando.
> Los documentos de cierre están en:
> - `docs/audits/fase0-seguridad.md`
> - `docs/audits/fase1-arquitectura.md`
> - `docs/audits/fase2-estado-eventos.md`
> - `docs/audits/plan-consolidado.md`
>
> Ahora ejecuta la FASE 3 — Display: thread-safety, rendimiento, touch robusto.
> Revisa `docs/audits/plan-consolidado.md` para los detalles de la fase.
>
> IMPORTANTE:
> - Lee los archivos relevantes antes de modificar nada
> - Ejecuta los tests (`python -m pytest backend/tests/ -v --tb=short`) después de cada cambio
> - Si algo rompe, arréglalo antes de continuar
> - No modifiques nada que no esté en esta lista
