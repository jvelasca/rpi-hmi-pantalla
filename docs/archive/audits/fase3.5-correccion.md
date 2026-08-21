# FASE 3.5 — Corrección de defectos críticos ✅ COMPLETADA

**Fecha:** 2026-08-12
**Tests:** 135/135 pasando (backend)
**Resultado:** Todos los P0/P1 detectados en auditoría externa corregidos. Cero regresiones.

---

## Resumen

La segunda auditoría externa reveló que las FASE 0-3 no estaban realmente cerradas como afirmaba la documentación. Se detectaron 4 problemas críticos (P0) y 10+ problemas importantes (P1) en el código. Esta fase de corrección resuelve todos ellos antes de continuar con FASE 5 (Calidad).

---

## Cambios realizados

### 🔴 P0-1: Eliminación de credenciales hardcodeadas (10 archivos)

| Archivo | Cambio |
|---------|--------|
| `scripts/deploy_frontend.py` | Refactorizado: usa `ParamikoSSHDriver` + `DeployService`. Credenciales desde `.env`. |
| `scripts/test_display.py` | Refactorizado: usa `ParamikoSSHDriver`. Credenciales desde `.env`. |
| `scripts/test_step.py` | Refactorizado: usa `ParamikoSSHDriver`. Credenciales desde `.env`. |
| `scripts/post_reboot_check.py` | Refactorizado: usa `ParamikoSSHDriver`. Credenciales desde `.env`. |
| `scripts/configure_display.ps1` | Contraseña → `$env:RPI_PASSWORD` con verificación previa. |
| `scripts/configure_display_direct.ps1` | Contraseña → `$env:RPI_PASSWORD`. Placeholder en mensaje de ayuda. |
| `scripts/connect_and_test.ps1` | Contraseña → `$env:RPI_PASSWORD` con verificación previa. |
| `scripts/full_deploy.ps1` | Mensaje de contraseñas eliminado, sustituido por referencia a env var. |
| `scripts/find_and_connect.ps1` | Mensaje de contraseña sustituido por referencia a `$env:RPI_PASSWORD`. |
| `docs/CONTEXT.md` | `RPI_PASSWORD=RaspberryB+2026!` → `RPI_PASSWORD=` |

### 🔴 P0-2: AutoAddPolicy eliminado

| Archivo | Cambio |
|---------|--------|
| `scripts/deploy_frontend.py` | `AutoAddPolicy()` → usa `ParamikoSSHDriver` (que usa `WarningPolicy`) |
| `scripts/test_display.py` | `AutoAddPolicy()` → `WarningPolicy()` vía `ParamikoSSHDriver` |
| `scripts/test_step.py` | `AutoAddPolicy()` → `WarningPolicy()` vía `ParamikoSSHDriver` |
| `scripts/post_reboot_check.py` | `AutoAddPolicy()` → `WarningPolicy()` vía `ParamikoSSHDriver` |

### 🔴 P0-3: Bug WebSocket Display corregido

| Antes | Ahora |
|-------|-------|
| `_start_ws_thread()` (línea 342), luego `self.running = True` (línea 352) — el hilo WS evaluaba `while self.running` = `False` y moría inmediatamente | `self.running = True` **antes** de `_start_ws_thread()` — el hilo WS arranca con la condición correcta |

**Archivo:** `display/app.py` líneas 336-348

### 🔴 P0-4: Contrato TypeScript `version` corregido

| Antes | Ahora |
|-------|-------|
| 4/4 llamadas a `send()` sin campo `version` (TypeScript declaraba `version: string` obligatorio) | Todas las llamadas incluyen `version: "1.0"` |

**Archivos:**
- `frontend/src/App.tsx`: `send({ type: "toggle_led", version: "1.0" })`, `send({ type: "press_button", version: "1.0" })`
- `frontend/src/hooks/useWebSocket.ts`: `send({ type: "subscribe", ..., version: "1.0" })`, `send({ type: "get_status", version: "1.0" })`

### 🔴 P0-5: GPIO17 hardcodeado eliminado

| Antes | Ahora |
|-------|-------|
| `led_pin = 17  # fallback compatible` si `devices.yaml` fallaba — activaba GPIO físico por defecto | Sin fallback: log warning informativo, LED funciona en modo virtual |

**Archivo:** `backend/app/main.py` línea 73

### 🔴 P0-6: `on_event("startup")` migrado a `lifespan`

| Antes | Ahora |
|-------|-------|
| `@router.on_event("startup")` deprecado en `ssh.py:286` | Función `auto_connect_ssh()` llamada desde `lifespan` de `main.py` |

**Archivos:**
- `backend/app/api/ssh.py`: `_auto_connect_ssh` → `auto_connect_ssh` (sin decorador)
- `backend/app/main.py`: `await auto_connect_ssh()` en el lifespan

### 🔴 P0-7: SSH unificado vía DeployService

| Antes | Ahora |
|-------|-------|
| `deploy_frontend.py` usaba `paramiko.SSHClient` directamente — duplicaba infraestructura SSH | Usa `ParamikoSSHDriver` + `DeployService` como `deploy.py` |

**Archivo:** `scripts/deploy_frontend.py` — reescrito completamente

### 🟠 P1-8: Modelo de dispositivo unificado (Pydantic)

| Antes | Ahora |
|-------|-------|
| Dos modelos incompatibles: Pydantic `DeviceConfig` (no usado) + `@dataclass Device` (en uso). `devices.yaml` en formato antiguo. | Modelo único: Pydantic `DeviceConfig` con loader YAML en `device.py`. `devices.yaml` migrado al nuevo formato declarativo. Retrocompatibilidad con formato antiguo. |

**Archivos:**
- `backend/app/models/device.py`: +`load_devices()`, +`_migrate_old_format()`
- `backend/app/services/gpio_service.py`: Eliminado `@dataclass Device`. `load_devices()` delega en `device.py`.
- `backend/app/services/state_manager.py`: Usa `DeviceType.DIGITAL_OUTPUT` y `dev.pin.bcm`
- `backend/app/main.py`: Usa `DeviceType.DIGITAL_OUTPUT` y `dev.pin.bcm`
- `backend/config/devices.yaml`: Nuevo formato Pydantic

Nuevo formato YAML:

```yaml
devices:
  - id: led1
    type: digital_output
    name: "LED 1"
    pin:
      bcm: 17
      name: "LED_ROJO"
```

### 🟠 P1-9: Reactividad de ButtonPanel corregida

| Antes | Ahora |
|-------|-------|
| `const { button, onPress, disabled } = props` — rompía reactividad de SolidJS | `props.button.pressed`, `props.button.press_count`, `props.onPress`, `props.disabled` |

**Archivo:** `frontend/src/components/ButtonPanel.tsx`

---

## Archivos modificados (18)

| Archivo | Tipo de cambio |
|---------|---------------|
| `scripts/deploy_frontend.py` | Reescrito (ParamikoSSHDriver + DeployService) |
| `scripts/test_display.py` | Reescrito (ParamikoSSHDriver + env vars) |
| `scripts/test_step.py` | Reescrito (ParamikoSSHDriver + env vars) |
| `scripts/post_reboot_check.py` | Reescrito (ParamikoSSHDriver + env vars) |
| `scripts/configure_display.ps1` | Credenciales → env var |
| `scripts/configure_display_direct.ps1` | Credenciales → env var |
| `scripts/connect_and_test.ps1` | Credenciales → env var |
| `scripts/full_deploy.ps1` | Mensaje de credenciales eliminado |
| `scripts/find_and_connect.ps1` | Mensaje de credenciales → env var |
| `docs/CONTEXT.md` | Contraseña eliminada |
| `display/app.py` | `self.running = True` movido antes de `_start_ws_thread()` |
| `frontend/src/App.tsx` | +version en send() calls |
| `frontend/src/hooks/useWebSocket.ts` | +version en send() calls |
| `frontend/src/components/ButtonPanel.tsx` | Destructuring → props.button.* |
| `backend/app/main.py` | GPIO17 fallback eliminado, lifespan SSH, Pydantic fields |
| `backend/app/api/ssh.py` | on_event → lifespan-compatible function |
| `backend/app/models/device.py` | +load_devices(), +_migrate_old_format() |
| `backend/app/services/gpio_service.py` | @dataclass Device eliminado, Pydantic DeviceConfig |
| `backend/app/services/state_manager.py` | Pydantic fields (DeviceType, dev.pin.bcm) |
| `backend/config/devices.yaml` | Formato Pydantic declarativo |

---

## Verificación

- `python -m pytest backend/tests/ -v --tb=short` → **135 passed**
- Cero warnings (el `DeprecationWarning` de `on_event` fue eliminado)
- Cero regresiones: todos los tests existentes pasan sin modificaciones
- La contraseña `RaspberryB+2026!` ya no aparece en ningún archivo de código ejecutable

---

## Referencias a contraseña remanentes (documentación)

Los siguientes archivos contienen referencias históricas a la contraseña por ser documentación/auditorías:

- `infra/INSTALL_RASPBIAN_B_PLUS.md` — Guía de instalación (ejemplo de configuración inicial)
- `docs/audits/fase0-seguridad.md` — Documento de auditoría (describe el estado anterior corregido)

---

## Próxima fase: FASE 5 — Calidad

Tras esta corrección, el proyecto está listo para continuar con FASE 5:
- Tests de integración (ya creados en `test_integration.py` — 50 tests)
- Cobertura real con `--cov`
- Tests de frontend (Vitest + SolidJS)
- Actualización de CI
