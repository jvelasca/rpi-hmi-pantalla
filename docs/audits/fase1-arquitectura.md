# FASE 1 — Unificación de arquitectura y limpieza ✅ COMPLETADA

**Fecha:** 2026-08-11
**Tests:** 121/121 pasando
**Resultado:** HAL unificada, legacy archivado, devices.yaml como fuente única, entry points unificados

---

## Cambios realizados

### 1. 🟠 Código legacy movido a `legacy/`

| Archivo | Origen | Destino |
|---------|--------|---------|
| `pi_hmi_server.py` | Raíz del proyecto | `legacy/pi_hmi_server.py` |
| `fb_ui.py` | Raíz del proyecto | `legacy/fb_ui.py` |
| `fb_test.py` | Raíz del proyecto | `legacy/fb_test.py` |
| `hal.py` | `backend/app/hardware/hal.py` | `legacy/hal.py` |

- Creado `legacy/README.md` documentando cada archivo y su razón de archivado
- `tests/test_fb_ui.py` actualizado para importar desde `legacy/`
- `backend/app/services/deploy_service.py`: eliminadas referencias a `backend/app/hardware/`

### 2. 🟠 HAL GPIO unificada (dos HALs → una)

| Antes | Ahora |
|-------|-------|
| `backend/app/hardware/hal.py` — HAL alternativa con `load_devices()` | Archivado en `legacy/hal.py` |
| `backend/app/services/gpio_service.py` — HAL principal con `gpiozero` | **Única HAL del proyecto** |

- `gpio_service.py` ahora incluye `Device` dataclass y `load_devices()` (absorbe funcionalidad de hal.py)
- `__all__` ampliado: `GPIOService`, `gpio_service`, `load_devices`, `Device`, `MockGPIODriver`, `RealGPIODriver`
- `diagnostics/gpio/blink_test.py` reescrito: usa `gpio_service.GPIOService` + `load_devices` en lugar de `hardware.hal`
- `backend/app/hardware/__init__.py` limpiado: placeholder para futuras HALs (I2C, SPI, PWM)

### 3. 🟠 `devices.yaml` como fuente única de verdad

| Antes | Ahora |
|-------|-------|
| `gpio_pin=17` hardcodeado en `LedState` (modelo) | `gpio_pin` cargado desde `devices.yaml` |
| `gpio_service.setup_output(17)` en `main.py` | `main.py` lee el pin desde `devices.yaml` al iniciar |
| `StateManager.__init__` con `gpio_pin=17` fijo | `StateManager._load_led_pin()` busca dispositivo GPIO output en YAML |

- `backend/app/models/hmi.py`: `gpio_pin` default cambió de `17` a `0`
- `backend/app/services/state_manager.py`: añadido `_load_led_pin()` que busca el primer dispositivo con `driver=gpio` y `mode=output` en `backend/config/devices.yaml`
- `backend/app/main.py`: lifespan lee pin desde `devices.yaml` con fallback a 17

### 4. 🟠 Entry points unificados

| Antes | Ahora |
|-------|-------|
| `Rpi_Pantalla_V1.py` con su propio argparse + `uvicorn.run("backend.app.main:app")` | **Wrapper** que importa la instancia `app` de `backend.app.main` |
| Dos entry points independientes con lógica duplicada | `backend/app/main.py` es el entry point **canónico** |

- `Rpi_Pantalla_V1.py` usa `uvicorn.run(app, ...)` pasando la instancia de FastAPI directamente
- Conserva misma interfaz CLI (`--host`, `--port`, `--reload`, `--log-level`)

### 5. 🟠 `scripts/deploy.py` refactorizado con `DeployService`

| Antes | Ahora |
|-------|-------|
| Raw `paramiko.SSHClient` con funciones `ssh()`, `sh()` propias | `ParamikoSSHDriver` para conexiones |
| Funciones `deploy()` y `install_deps()` con SFTP manual | `DeployService.deploy_app()` para despliegue del backend |
| Lógica SSH/SFTP duplicada entre `scripts/deploy.py` y `DeployService` | `DeployService` es el único componente con lógica de despliegue |

- `scripts/deploy.py` elimina ~100 líneas de lógica SSH/SFTP duplicada
- Misma interfaz CLI: `--run`, `--hmi`, `--verify`, `--install-service`
- Funciones específicas del display (`deploy_display_files`, `install_display_deps`, `stop_lightdm`, etc.) se mantienen en el script

---

## Archivos modificados (11)

| Archivo | Tipo de cambio |
|---------|---------------|
| `legacy/pi_hmi_server.py` | Movido desde raíz |
| `legacy/fb_ui.py` | Movido desde raíz |
| `legacy/fb_test.py` | Movido desde raíz |
| `legacy/hal.py` | Movido desde `backend/app/hardware/` |
| `legacy/README.md` | Nuevo: documentación del código histórico |
| `backend/app/services/gpio_service.py` | +Device, +load_devices, exports ampliados |
| `backend/app/hardware/__init__.py` | Limpiada referencia a hal.py |
| `backend/app/services/deploy_service.py` | Eliminadas refs a hardware/hal.py |
| `backend/app/services/state_manager.py` | +_load_led_pin() desde devices.yaml |
| `backend/app/models/hmi.py` | gpio_pin default 17 → 0 |
| `backend/app/main.py` | lifespan lee pin desde devices.yaml |
| `diagnostics/gpio/blink_test.py` | Usa gpio_service unificado |
| `scripts/deploy.py` | Usa ParamikoSSHDriver + DeployService |
| `Rpi_Pantalla_V1.py` | Simplificado a wrapper |
| `tests/test_fb_ui.py` | Importa desde legacy/ |

---

## Post-fase: verificación

- `python -m pytest backend/tests/ tests/ -v --tb=short` → **121 passed**
- Todos los archivos Python compilan sin errores de sintaxis
- `legacy/` contiene 4 archivos + README.md
- `backend/app/hardware/hal.py` ya no existe en la ruta original

---

## Próxima fase: FASE 2 — Estado y eventos

**Prompt para el siguiente chat:**

> Continuamos el plan de trabajo consolidado para el proyecto Rpi_Pantalla_V1 (Raspberry Pi HMI).
>
> La FASE 0 (Seguridad) y FASE 1 (Arquitectura) están completadas — 121/121 tests pasando, 11+ archivos modificados.
> Los documentos de cierre están en:
> - `docs/audits/fase0-seguridad.md`
> - `docs/audits/fase1-arquitectura.md`
> - `docs/audits/plan-consolidado.md`
>
> Ahora ejecuta la FASE 2 — Estado y eventos:
> 1. Corregir `ws_count` en `SystemStatus` (actualmente cuenta subscribers por topic en vez de clientes únicos)
> 2. Corregir `uptime_seconds` (actualmente usa `time.monotonic()` que devuelve tiempo desde boot, no desde arranque del servicio)
> 3. Versionar el protocolo WebSocket (añadir campo `version` a todos los mensajes)
>
> IMPORTANTE:
> - Lee los archivos relevantes antes de modificar nada
> - Ejecuta los tests (`python -m pytest backend/tests/ -v --tb=short`) después de cada cambio
> - Si algo rompe, arréglalo antes de continuar
> - No modifiques nada que no esté en esta lista
