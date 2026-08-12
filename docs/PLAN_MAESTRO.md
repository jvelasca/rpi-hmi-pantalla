# PLAN MAESTRO — Consolidación RPi HMI v0.3.0

> **Estado actual:** v0.2.0/v0.3.0 inconsistente — proyecto funcional pero con defectos de
> integración, deploy y versionado.
> **Objetivo:** Versión 0.3.0 unificada, limpia, desplegable, con deploy corregido, sin bugs
> de concurrencia, y con hardening de seguridad.
> **Fecha:** 2026-08-12

---

## Problema detectado

Dos auditorías independientes (externa + propia) han verificado **34 problemas** en el
proyecto. El backend es sólido pero el sistema de deploy está fragmentado, hay bugs de
concurrencia en WebSocket, la seguridad tiene una superficie de ataque innecesaria, y
la versión es inconsistente entre los distintos componentes.

## Filosofía de ejecución

El trabajo se divide en **5 chats independientes** para evitar sobrecarga del contexto.
Cada chat:

1. Recibe un **documento de handoff** con instrucciones precisas
2. Ejecuta sus tareas (solo lectura de archivos y edición de código)
3. Produce un **documento de finalización** con el resumen de cambios
4. Escribe un **texto de handoff** para pasar al siguiente chat

**Principio clave:** Cada chat opera de forma autónoma sobre su alcance definido.
No se mezclan fases. Si un chat detecta un problema fuera de su scope, lo documenta
pero no lo corrige.

---

## División en 5 chats

### Chat 1: Fase A — Limpieza inmediata y unificación de versión

**Archivos a modificar:**
| Archivo | Cambio |
|---------|--------|
| `frontend/Untitled` | ELIMINAR |
| `VERSION` | `0.2.0` → `0.3.0` |
| `backend/pyproject.toml` | `0.2.0` → `0.3.0` |
| `backend/app/main.py` (líneas 159, 203) | `0.2.0` → `0.3.0` |
| `frontend/package.json` | `0.1.0` → `0.3.0` |
| `backend/app/services/ssh_manager.py` (línea 244) | Corregir log |
| Todos los `__pycache__/` | ELIMINAR |
| `README.md` | Actualizar versión y conteo de tests |

**Duración estimada:** 30-45 min

---

### Chat 2: Fase B — Corrección del flujo de deploy

**Archivos a modificar:**
| Archivo | Cambio |
|---------|--------|
| `scripts/deploy.py` | Reordenar: deploy → restart → health. Eliminar ensure_backend antes. Añadir restart. Integrar frontend. |
| `backend/app/services/deploy_service.py` | Añadir frontend a DEPLOY_DIRECTORIES y extensiones permitidas |
| `scripts/setup_rpi.sh` | Actualizar PROJECT_DIR y VENV_DIR a nueva arquitectura |
| `infra/INSTALL_RASPBIAN_B_PLUS.md` | Actualizar nombres de servicios y rutas |

**Duración estimada:** 45-60 min

---

### Chat 3: Fase C — Bugs de concurrencia WebSocket

**Archivos a modificar:**
| Archivo | Cambio |
|---------|--------|
| `backend/app/services/state_manager.py` | `set_led()`: mover `seq = self._sequence` dentro del lock |
| `backend/app/services/state_manager.py` | `press_button()`: mover `seq = self._sequence` dentro del lock |
| `backend/app/services/state_manager.py` | `release_button()`: mover `seq = self._sequence` dentro del lock |
| `backend/app/services/state_manager.py` | `set_display()`: añadir `self._sequence += 1` antes del broadcast |

**Duración estimada:** 15-20 min

---

### Chat 4: Fase D — Hardening de seguridad

**Archivos a modificar:**
| Archivo | Cambio |
|---------|--------|
| `backend/app/main.py` | Feature-gate para admin routers (ENABLE_ADMIN_API) |
| `backend/app/config.py` | Añadir `enable_admin_api` setting + validación API key |
| `backend/app/services/ssh_manager.py` | Corregir log "WarningPolicy" → "RejectPolicy" |
| `.env.example` | Añadir advertencia documentada |

**Duración estimada:** 30-45 min

---

### Chat 5: Fase E — Robustez y refinamiento

**Archivos a modificar:**
| Archivo | Cambio |
|---------|--------|
| `display/app.py` | Reducir polling REST cuando WS conectado (3-5s fallback) |
| `display/ui/touch.py` | Eliminar fallback ciego `candidates[0]`, obtener capacidades de evdev |
| `backend/requirements.txt` | Separar runtime/display/dev |
| `backend/__init__.py` | Vaciar |
| `backend/app/__init__.py` | Vaciar |
| `frontend/src/hooks/useWebSocket.ts` | Añadir validación runtime de mensajes WS |
| `frontend/src/App.tsx` | `gpio_pin: 0` como estado inicial (no hardcodear 17) |
| `display/app.py` (línea 267) | Añadir `version: "1.0"` al subscribe WS |
| `backend/app/api/health.py` | Simplificar _check_db duplicado |

**Duración estimada:** 60-90 min

---

## Orden de ejecución

```
Chat 1 (Fase A) ──► Chat 2 (Fase B) ──► Chat 3 (Fase C) ──► Chat 4 (Fase D) ──► Chat 5 (Fase E)
```

Las dependencias son:

- **Chat 1** es requisito para todos: unifica la versión y limpia el repo
- **Chat 2** depende de Chat 1 (usa la versión unificada)
- **Chat 3** es independiente (solo modifica state_manager.py)
- **Chat 4** depende de Chat 1 (usa config.py limpio)
- **Chat 5** depende de todos los anteriores (es el refinamiento final)

## Documentos generados

Cada chat producirá:

1. `docs/handoffs/CHAT_1_A_RESULTADO.md` (con handoff para Chat 2)
2. `docs/handoffs/CHAT_2_B_RESULTADO.md` (con handoff para Chat 3)
3. `docs/handoffs/CHAT_3_C_RESULTADO.md` (con handoff para Chat 4)
4. `docs/handoffs/CHAT_4_D_RESULTADO.md` (con handoff para Chat 5)
5. `docs/handoffs/CHAT_5_E_RESULTADO.md` (documento de cierre)

Los handoffs de entrada ya están creados en:

- `docs/handoffs/CHAT_1_A_LIMPIEZA.md`
- `docs/handoffs/CHAT_2_B_DEPLOY.md`
- `docs/handoffs/CHAT_3_C_CONCURRENCIA.md`
- `docs/handoffs/CHAT_4_D_SEGURIDAD.md`
- `docs/handoffs/CHAT_5_E_ROBUSTEZ.md`

## Verificación final

Tras completar los 5 chats, se debe verificar:

- [ ] `VERSION` = `0.3.0`
- [ ] `pyproject.toml` root = `0.3.0`
- [ ] `backend/pyproject.toml` = `0.3.0`
- [ ] `backend/app/main.py` version = `0.3.0`
- [ ] `frontend/package.json` = `0.3.0`
- [ ] No existen `__pycache__/` ni `*.pyc` en el repo
- [ ] No existe `frontend/Untitled`
- [ ] `scripts/deploy.py` reinicia el backend tras copiar archivos
- [ ] `DepoyService` incluye frontend
- [ ] `state_manager.py` no tiene race condition en sequence
- [ ] `set_display()` incrementa sequence
- [ ] Admin endpoints están protegidos por feature gate
- [ ] `ssh_manager.py` log dice "RejectPolicy"
- [ ] `setup_rpi.sh` usa rutas nuevas
- [ ] `INSTALL_RASPBIAN_B_PLUS.md` usa nombres de servicios nuevos
- [ ] `README.md` refleja versión 0.3.0
- [ ] Display no hace polling REST cada 500ms con WS conectado
- [ ] Touch no usa fallback ciego a event0
- [ ] `backend/requirements.txt` está separado por categorías
- [ ] `backend/__init__.py` y `backend/app/__init__.py` están vacíos
- [ ] Frontend tiene validación runtime de mensajes WS
- [ ] `gpio_pin: 0` en App.tsx estado inicial
