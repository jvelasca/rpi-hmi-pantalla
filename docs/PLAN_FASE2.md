# PLAN FASE 2 — Correcciones de Auditoría v0.3.0 → v0.3.1

> **Origen:** Auditoría externa sobre el commit `c7bfa2f` (v0.3.0 consolidada)
> **Veredicto auditoría:** 29/30 checks pasados. El proyecto está maduro pero 3 problemas
> estructurales impiden el `9/10`: deploy no transaccional, carrera StateManager, y
> persistencia sin drain/rollback.
> **Objetivo:** Corregir los 16 problemas detectados en 4 chats paralelos.
> **Fecha:** 2026-08-12

---

## Hallazgos de la auditoría y su clasificación

### 🔴 P0 — Bloqueantes (antes de tocar hardware real)

| # | Problema | Ubicación |
|---|----------|-----------|
| 1 | Deploy no llama a `setup_environment()` — falla en Pi nueva (sin venv) | `scripts/deploy.py:main()` |
| 2 | Deploy no aborta si algún archivo falla al transferir | `scripts/deploy.py` + `deploy_service.py` |
| 3 | `install_display_deps()` instala `websocket` en vez de `websocket-client` | `scripts/deploy.py:150` |
| 4 | `set_led()` lee `self._led_state` fuera del lock (callback/broadcast/return) | `state_manager.py:181,191,198` |

### 🟠 P1 — Importantes (antes de considerar release)

| # | Problema | Ubicación |
|---|----------|-----------|
| 5 | Persistencia: `asyncio.create_task()` sin drain en shutdown | `state_manager.py` + `main.py` lifespan |
| 6 | `event_log` crece indefinidamente (sin rotación) | `persistence.py` |
| 7 | Touch: fallback a `event0` vía `preferred` parameter | `touch.py:60-61` |
| 8 | systemd: `Documentation=https://github.com/user/rpi_hmi` (repo inexistente) | `*.service` línea 3 |
| 9 | README: formato roto, IPs hardcodeadas, conteo tests inconsistente | `README.md` |
| 10 | Deploy no es atómico (sin releases/ + current symlink) | `deploy.py` (nuevo script) |

### 🟡 P2 — Refinamiento

| # | Problema | Ubicación |
|---|----------|-----------|
| 11 | `pyproject.toml` + `requirements.txt` duplican declaración de dependencias | `backend/` |
| 12 | CI no hace smoke test del artefacto de release | `.github/workflows/` |
| 13 | `led_device_id` no es configurable (coge el primer digital_output) | `state_manager.py:_load_led_pin()` |
| 14 | Frontend no usa `sequence` para detectar gaps | `useWebSocket.ts` |
| 15 | Frontend: validación runtime parcial (solo type, no estructura completa) | `useWebSocket.ts` |
| 16 | `INSTALL_RASPBIAN_B_PLUS.md` tiene IPs hardcodeadas | `infra/` |

---

## División en 4 chats paralelos

### Chat 6: Deploy (P0 #1, #2, #3)

**Archivos:** `scripts/deploy.py`

1. Llamar a `deploy_svc.setup_environment()` al inicio del flujo default
2. Abortar si `deploy_svc.deploy_app()` devuelve pasos con `success=False`
3. Cambiar `install_display_deps()` para usar `pip install -r display/requirements.txt` en vez de módulo-por-módulo con `websocket`

### Chat 7: StateManager (P0 #4)

**Archivos:** `backend/app/services/state_manager.py`

1. En `set_led()`: capturar `new_state = self._led_state` (copia) dentro del lock, usar `new_state` para callback, persistencia, broadcast y return
2. Mismo patrón en `press_button()`, `release_button()`, `set_display()`

### Chat 8: Persistencia + Hardening (P1 #5, #6, #7, #8, #9)

**Archivos:** `persistence.py`, `state_manager.py`, `main.py`, `touch.py`, `*.service`, `README.md`

1. Persistencia: drain de `pending_tasks` en shutdown (`main.py` lifespan)
2. `event_log`: rotación (`MAX_EVENT_LOG_ROWS = 10000`)
3. Touch: eliminar fallback a `preferred`/event0 (retornar None si no se detecta touch)
4. systemd: cambiar `Documentation` a `https://github.com/jvelasca/rpi-hmi-pantalla`
5. README: corregir formato, IPs, conteo tests
6. `INSTALL_RASPBIAN_B_PLUS.md`: quitar IPs hardcodeadas

### Chat 9: Atomic Deploy + CI (P1 #10, P2 #11, #12, #13, #14, #15)

**Archivos:** nuevo `scripts/deploy_atomic.py`, `backend/requirements.txt`, `pyproject.toml`, `.github/workflows/ci.yml`, `state_manager.py`, `useWebSocket.ts`

1. Nuevo script `deploy_atomic.py`: releases/ dir + current symlink + rollback
2. Sincronizar `requirements.txt` con `pyproject.toml` extras
3. CI: añadir job `release-smoke` que verifique estructura del artefacto
4. `state_manager.py`: hacer `led_device_id` configurable via `devices.yaml`
5. Frontend: usar `sequence` para detectar gaps y resync
6. Frontend: mejorar validación runtime (campos requeridos, no solo type)

---

## Verificación final

Tras los 4 chats, verificar:

- [ ] `scripts/deploy.py` llama a `setup_environment()` antes del deploy en flujo default
- [ ] `scripts/deploy.py` aborta si `deploy_app()` tiene errores
- [ ] `install_display_deps()` usa `pip install -r display/requirements.txt`
- [ ] `state_manager.py`: `set_led()` captura copia dentro del lock
- [ ] `state_manager.py`: `set_display()`, `press_button()`, `release_button()` capturan copia
- [ ] `persistence.py`: `event_log` tiene rotación con MAX_EVENT_LOG_ROWS
- [ ] `main.py` lifespan: drain de tareas pendientes antes de `close_persistence()`
- [ ] `touch.py`: no hay fallback a event0
- [ ] `*.service`: `Documentation` apunta a repo real
- [ ] `README.md`: sin formato roto, sin IPs hardcodeadas, conteo tests coherente
- [ ] `scripts/deploy_atomic.py` existe y tiene releases/ + current → symlink
- [ ] `requirements.txt` sincronizado con `pyproject.toml`
- [ ] CI: job `release-smoke` existe
- [ ] Frontend: usa sequence para detectar gaps
- [ ] Frontend: validación runtime de estructura completa
