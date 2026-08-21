# FASE 6 — Persistencia, Health Check y Tipos OpenAPI

**Fecha:** 2026-08-12  
**Estado:** COMPLETADA  
**Plan:** plan-consolidado.md § FASE 6

---

## 1. Resultados de Tests

| Métrica | Valor |
|---------|-------|
| Tests totales backend + display | **182** |
| Pasaron | **182** (100%) |
| Fallaron | 0 |
| Nuevos tests FASE 6 | **12** (8 persistencia + 4 health endpoint) |

---

## 2. Persistencia SQLite

### Módulo: `backend/app/services/persistence.py`

Capa de persistencia asíncrona con `aiosqlite`:

| Funcionalidad | Descripción |
|--------------|-------------|
| `init()` | Crea BD + tablas (`led_state`, `button_state`, `event_log`) con migración inline |
| `save_led(state, gpio_pin)` / `get_led()` | Persiste/recupera estado del LED |
| `save_button_count(count)` / `get_button_count()` | Persiste/recupera contador de pulsaciones |
| `log_event(type, payload)` / `get_recent_events(limit)` | Log histórico de eventos con timestamp UTC |
| `is_healthy()` | Verifica conectividad con `SELECT 1` |
| `get_persistence(db_path)` | Factory singleton asíncrono |
| `close_persistence()` | Cierre limpio en shutdown |

### Integración con StateManager

```python
# En lifespan (main.py):
db = await get_persistence(settings.db_path)
state_manager.set_persistence(db)
await state_manager.restore_from_db()  # Recupera LED + contador tras reinicio

# En cada mutación (state_manager.py):
self._persist_led(state)   # asyncio.create_task en background
self._persist_button(count)
```

El estado sobrevive reinicios del servidor: el LED recupera su último estado y el contador de pulsaciones se mantiene acumulativo.

---

## 3. Health Check Robusto

### Nuevo endpoint: `GET /health`

Reemplaza el viejo `{"status": "ok"}` por un modelo Pydantic completo:

| Campo | Descripción |
|-------|-------------|
| `status` | `healthy`, `degraded` o `unhealthy` (según todos los checks) |
| `checks.api` | API operativa (siempre `pass`) |
| `checks.uptime` | Horas de uptime |
| `checks.gpio` | Pin GPIO configurado (`pass`) o modo virtual (`warn`) |
| `checks.display` | Display conectado (`pass`) o no detectado (`warn`) |
| `checks.db` | SQLite operativa (`pass`) o no disponible (`warn`) |
| `checks.cpu` | Temperatura CPU (alerta `warn` si >80°C) |
| `checks.ws` | Clientes WebSocket conectados |
| `timestamp` | UTC |
| `uptime_seconds` | Segundos desde arranque |

Si el estado global es `unhealthy`, el endpoint devuelve **HTTP 503**.

### Modelos OpenAPI

```python
class HealthCheckDetail(BaseModel):
    status: Literal["pass", "warn", "fail"]
    message: str

class HealthStatus(BaseModel):
    status: Literal["healthy", "degraded", "unhealthy"]
    checks: dict[str, HealthCheckDetail]
    timestamp: datetime
    uptime_seconds: float
```

Todos los campos tienen `Field(description=...)` para documentación OpenAPI automática.

---

## 4. Cambios en archivos

| Archivo | Cambio |
|---------|--------|
| `backend/app/services/persistence.py` | **Nuevo** — capa SQLite con aiosqlite |
| `backend/app/api/health.py` | **Nuevo** — endpoint health con Pydantic models |
| `backend/app/models/hmi.py` | Sin cambios (modelos existentes suficientes) |
| `backend/app/models/events.py` | Sin cambios |
| `backend/app/services/state_manager.py` | Añadidos `set_persistence()`, `restore_from_db()`, `_persist_led()`, `_persist_button()` |
| `backend/app/config.py` | Añadido `db_path` (default: `data/state.db`) |
| `backend/app/api/__init__.py` | Añadido `health_router` |
| `backend/app/main.py` | Inicialización/cierre de persistencia en lifespan. Health router registrado. Eliminado viejo `/health` bare endpoint. |
| `backend/tests/conftest.py` | **Nuevo** — fixtures `client`, `async_client`, `reset_state` (extraídas de `test_hmi.py`) |
| `backend/tests/test_persistence.py` | **Nuevo** — 12 tests (8 persistencia + 4 health endpoint) |
| `backend/tests/test_hmi.py` | Health tests actualizados al nuevo formato |
| `backend/tests/test_integration.py` | `test_health_check` actualizado |
| `backend/requirements.txt` | Añadido `aiosqlite>=0.20.0` |
| `.gitignore` | Añadidos `data/`, `*.db`, `*.sqlite` |
| `.env.example` | IP actualizada a `192.168.88.211` |

---

## 5. Resumen del Plan Consolidado

| Fase | Estado |
|------|--------|
| 🔴 FASE 0 — Seguridad | ✅ COMPLETADA |
| 🟠 FASE 1 — Arquitectura | ✅ COMPLETADA |
| 🟠 FASE 2 — Estado/Eventos | ✅ COMPLETADA |
| 🟠 FASE 3 — Display | ✅ COMPLETADA |
| 🟠 FASE 3.5 — Corrección P0/P1 | ✅ COMPLETADA |
| 🟡 FASE 4 — Deploy/CI | ✅ COMPLETADA |
| 🟢 FASE 5 — Calidad | ✅ COMPLETADA |
| 🟢 FASE 6 — Persistencia | ✅ COMPLETADA |

**Todas las fases del plan consolidado están COMPLETADAS.** 🎉
