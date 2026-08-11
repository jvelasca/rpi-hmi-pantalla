# FASE 0 — Seguridad ✅ COMPLETADA

**Fecha:** 2026-08-11
**Tests:** 77/77 pasando
**Resultado:** Todas las vulnerabilidades críticas corregidas

---

## Cambios realizados

### 1. 🔴 Eliminación de credenciales hardcodeadas

| Archivo | Cambio |
|---------|--------|
| `scripts/deploy.py` | Antes: `PASSWORD = "RaspberryB+2026!"` hardcodeado. Ahora: lee `RPI_PASSWORD` o `RPI_KEY_PATH` de `.env` via `python-dotenv`. También cambiado `AutoAddPolicy` → `WarningPolicy`. |
| `.env` | Contraseña vaciada (`RPI_PASSWORD=`). Añadidas variables de seguridad: `ADMIN_API_KEY`, `CORS_ORIGINS`, `ENABLE_DOCS`. |
| `.env.example` | Eliminada la contraseña de ejemplo. Usa placeholders vacíos. |
| `backend/app/services/ssh_manager.py` | Docstring: eliminada contraseña de ejemplo `"RaspberryB+2026!"` → `"your_password"`. |

### 2. 🔴 Eliminación de `GET /api/ssh/exec?cmd=...`

- **Eliminado completamente.** El endpoint más peligroso (RCE vía GET con query parameter) ya no existe.
- `POST /admin/ssh/execute` permanece, pero protegido por API key (ver punto 3).

### 3. 🔴 Separación API HMI / API Administrativa + Auth

| Antes | Ahora |
|-------|-------|
| `POST /api/ssh/connect` | `POST /admin/ssh/connect` (requiere `X-API-Key`) |
| `POST /api/ssh/execute` | `POST /admin/ssh/execute` (requiere `X-API-Key`) |
| `POST /api/deploy/setup` | `POST /admin/deploy/setup` (requiere `X-API-Key`) |
| Todos `/api/deploy/*` | Todos `/admin/deploy/*` (requiere `X-API-Key`) |

- **Autenticación:** Todos los endpoints `/admin/*` verifican el header `X-API-Key` contra `ADMIN_API_KEY` en `.env`.
- Si `ADMIN_API_KEY` no está configurada, los endpoints devuelven 503.
- La API HMI (`/api/status`, `/api/led/*`, `/api/button/*`, `/ws`) sigue sin autenticación (diseñada para LAN local).

### 4. 🟠 CORS cerrado

| Antes | Ahora |
|-------|-------|
| `allow_origins=["*"]` | `allow_origins=settings.cors_origin_list` (configurable vía `.env`) |
| `allow_credentials=True` | `allow_credentials=False` |
| `allow_methods=["*"]` | `allow_methods=["GET", "POST"]` |
| `allow_headers=["*"]` | `allow_headers=["Content-Type", "Accept"]` |

- Default: `http://localhost:5173,http://localhost:8000`
- Configurable en `.env`: `CORS_ORIGINS=http://localhost:5173,http://192.168.88.211:8000`

### 5. 🟡 SSH: `AutoAddPolicy` → `WarningPolicy`

- `ParamikoSSHDriver.connect()` ahora usa `paramiko.WarningPolicy()` en lugar de `AutoAddPolicy()`.
- **WarningPolicy** acepta la clave pero emite advertencia en logs, permitiendo detectar cambios de host key.
- Para entornos con requisitos estrictos, usar `RejectPolicy` + archivo `known_hosts`.

### 6. 🔴 Systemd hardening

**rpi-hmi-backend.service:**
- `After=network-online.target` + `Wants=network-online.target` (antes `network.target`)
- Añadido hardening: `NoNewPrivileges=true`, `PrivateTmp=true`, `ProtectSystem=strict`, `ProtectHome=true`, `ProtectKernelTunables=true`, `ProtectKernelModules=true`, `ProtectControlGroups=true`, `RestrictSUIDSGID=true`, `LockPersonality=true`
- `ReadWritePaths` limitado a rutas necesarias

**rpi-hmi-display.service:**
- `User=root` → **`User=pi`** con `SupplementaryGroups=video,input,render`
- `After=network-online.target` (antes `network.target`)
- **`ExecStartPre=/bin/sleep 3` eliminado** → sustituido por `curl` health check loop (espera hasta 30s a que el backend responda)
- Añadido hardening: `NoNewPrivileges=true`, `PrivateTmp=true`, `ProtectHome=true`, `RestrictSUIDSGID=true`, `LockPersonality=true`

### 7. 🟢 `/docs` deshabilitado en producción

- Nueva variable `ENABLE_DOCS` en `.env` (default: `false`)
- Cuando `ENABLE_DOCS=false`: `docs_url=None`, `redoc_url=None`
- En desarrollo, establecer `ENABLE_DOCS=true` para acceder a Swagger UI

---

## Archivos modificados (11)

| Archivo | Tipo de cambio |
|---------|---------------|
| `.env` | Credenciales vaciadas, nuevas vars de seguridad |
| `.env.example` | Contraseña placeholder, sin valor real |
| `backend/app/config.py` | Añadidos `admin_api_key`, `cors_origins`, `enable_docs` |
| `backend/app/main.py` | CORS cerrado, `/docs` condicional, routers admin registrados |
| `backend/app/api/__init__.py` | Añadidos `admin_ssh_router`, `admin_deploy_router` |
| `backend/app/api/ssh.py` | Prefix `/admin/ssh`, API key auth, GET `/exec` eliminado |
| `backend/app/api/deploy.py` | Prefix `/admin/deploy`, API key auth |
| `backend/app/services/ssh_manager.py` | `AutoAddPolicy` → `WarningPolicy`, docstring limpio |
| `scripts/deploy.py` | Credenciales desde `.env`, `WarningPolicy` |
| `config/systemd/rpi-hmi-backend.service` | `network-online`, hardening |
| `config/systemd/rpi-hmi-display.service` | `User=pi`, `sleep 3` → health check, hardening |
| `Rpi_Pantalla_V1.py` | Docstring actualizado con nuevas rutas |

---

## Post-fase: pasos manuales requeridos

1. **Cambiar la contraseña SSH de la Raspberry Pi** si `RaspberryB+2026!` era real:
   ```bash
   ssh pi@192.168.88.211
   passwd
   ```

2. **Configurar `ADMIN_API_KEY`** en el `.env` de la Pi:
   ```
   ADMIN_API_KEY=tu-clave-segura-unica
   ```

3. **Verificar que `.env` NO está en git:**
   ```bash
   git log -- .env
   ```
   Si aparece en el historial, usar `git filter-branch` o `BFG Repo-Cleaner` para eliminarlo.

4. **Reinstalar servicios systemd** en la Pi tras los cambios:
   ```bash
   python scripts/deploy.py --install-service
   ```

5. **Verificar que el display funciona como `User=pi`:**
   ```bash
   ssh pi@192.168.88.211
   sudo systemctl status rpi-hmi-display
   ```
   Si falla por permisos DRM, verificar grupos: `groups pi` debe incluir `video`, `input`, `render`.

---

## Próxima fase: FASE 1 — Unificación de arquitectura y limpieza

**Prompt para el siguiente chat:**

> Continuamos el plan de trabajo consolidado para Rpi_Pantalla_V1. La FASE 0 (Seguridad) está completada y verificada con 77/77 tests pasando. El documento de cierre está en `docs/audits/fase0-seguridad.md`.
>
> Ahora ejecuta la FASE 1 — Unificación de arquitectura y limpieza:
> 1. Mover código legacy (`pi_hmi_server.py`, `fb_ui.py`, `fb_test.py`) a carpeta `legacy/`
> 2. Unificar las dos HAL GPIO (mantener solo `gpio_service.py`, archivar `hardware/hal.py`)
> 3. Hacer que `devices.yaml` sea la fuente de verdad (eliminar GPIO17 hardcodeado)
> 4. Unificar entry points del backend
> 5. Refactorizar `scripts/deploy.py` para usar `DeployService`
>
> Lee los archivos relevantes primero, NO modifiques nada sin leer, y ejecuta los tests después de cada cambio.
