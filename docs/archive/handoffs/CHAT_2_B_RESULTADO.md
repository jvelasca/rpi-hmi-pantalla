# CHAT 2 — Fase B: Corrección del Flujo de Deploy — RESULTADO

**Fecha:** 2026-08-12
**Versión:** 0.3.0

---

## Resumen de cambios

### 1. scripts/deploy.py — Flujo de deploy corregido

- **Flujo por defecto:** Eliminada la llamada `ensure_backend(ssh)` del principio (antes del deploy). Ahora el orden es: deploy → restart_backend() → espera /health/ready (30 intentos, 1s cada uno) → restart display → verify.
- **Flujo `--install-service`:** Añadido `_deploy_frontend_static()` tras `deploy_scripts()`. Añadido `restart_backend()` + health check al final.
- **Flujo `--hmi`:** Añadido `_deploy_frontend_static()` tras `deploy_scripts()`. Añadido `deploy_svc.restart_backend()` antes de `run_hmi(ssh)`.
- **Función `_deploy_frontend_static()`:** Nueva función que compila el frontend con `npm run build` (si `dist/index.html` no existe) y copia `frontend/dist/` a `{PI_BASE}/backend/app/static/` vía SFTP.
- **`import subprocess`** añadido al inicio del archivo.

### 2. backend/app/services/deploy_service.py — Extensiones y directorios

- `DEPLOY_DIRECTORIES`: añadido `"frontend/dist"` a la lista.
- `allowed_extensions`: ampliado con `.js`, `.css`, `.html`, `.svg`, `.ico`, `.woff2`.

### 3. scripts/setup_rpi.sh — Rutas actualizadas

- `PROJECT_DIR` cambiado de `/home/pi/Rpi_Pantalla_V1` → `/home/pi/rpi_hmi`.
- `VENV_DIR` cambiado de `$PROJECT_DIR/.venv` → `$PROJECT_DIR/venv` (incluyendo mensajes de log).
- FASE 10: `nohup` reemplazado por `sudo systemctl start rpi-hmi-backend.service` con fallback a nohup.
- Banner/título se mantiene (incluye `Rpi_Pantalla_V1` como nombre de proyecto).

### 4. infra/INSTALL_RASPBIAN_B_PLUS.md — Referencias actualizadas

- Todas las referencias a `hmi-backend.service` → `rpi-hmi-backend.service`.
- Todas las rutas `/home/pi/Rpi_Pantalla_V1` → `/home/pi/rpi_hmi`.
- Todos los `.venv` en rutas → `venv`.
- FASE 7: clone paths actualizados (`rpi_hmi`, `venv`).
- FASE 10: contenido del servicio systemd actualizado con `WorkingDirectory=/home/pi/rpi_hmi` y `ExecStart=/home/pi/rpi_hmi/venv/bin/python3`.
- Añadido `rpi-hmi-display.service` en comandos de enable/start/status.

---

## Resultados de verificación

| Verificación | Resultado |
|---|---|
| `ensure_backend` no se llama en flujo default | Solo permanece como definición de función |
| `restart_backend` en deploy.py | 3 ocurrencias: install-service, hmi, default |
| DeployService incluye frontend | `frontend/dist` en DEPLOY_DIRECTORIES |
| setup_rpi.sh sin rutas antiguas | Solo `Rpi_Pantalla_V1` en el banner |
| INSTALL doc sin `hmi-backend` antiguo | Todas usan `rpi-hmi-backend` |
| Python syntax check deploy.py | Compila OK |
| Python syntax check deploy_service.py | Compila OK |

---

## Incidencias

Ninguna. Todos los cambios aplicados sin conflictos.
