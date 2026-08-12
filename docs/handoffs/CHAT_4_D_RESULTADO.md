# CHAT 4 — Fase D: Hardening de Seguridad — RESULTADO

**Fecha:** 2026-08-12
**Estado:** Completado

---

## Resumen de cambios

### 1. `backend/app/config.py` — Nuevo campo `enable_admin_api`

Añadido después de `enable_docs` (línea 62-67):

```python
enable_admin_api: bool = Field(
    default=False,
    description="Habilitar endpoints administrativos /admin/* (SSH, deploy). "
                "SOLO para desarrollo.",
)
```

### 2. `backend/app/config.py` — Validador `model_post_init`

Añadido método `model_post_init` a la clase `Settings` (líneas 83-104) que valida la API key al iniciar:

- `enable_admin_api=True` y `admin_api_key` vacía → `logging.critical("ADMIN_API_KEY no configurada")`
- `admin_api_key == "cambia-esto-por-una-clave-segura"` → `logging.critical("clave por defecto")`
- `len(admin_api_key) < 16` y no vacía → `logging.warning("clave corta")`

### 3. `backend/app/main.py` — Feature-gate de routers admin

Líneas 181-185: Los routers `admin_ssh_router` y `admin_deploy_router` ahora solo se incluyen si `settings.enable_admin_api=True`. Se emite un `logger.warning` cuando están habilitados.

### 4. `backend/app/main.py` — Auto-conexión SSH condicionada

Líneas 113-120: La llamada a `auto_connect_ssh()` dentro del lifespan ahora está envuelta en `if settings.enable_admin_api:`.

### 5. `.env.example` — Actualizado

- Añadido `ENABLE_ADMIN_API=false` (nuevo)
- Añadidas advertencias de seguridad con ⚠️ sobre endpoints `/admin/*`
- Instrucciones para generar clave segura: `python -c "import secrets; print(secrets.token_urlsafe(32))"`

---

## Verificación

```
✓ Config tiene enable_admin_api                            (3 matches)
✓ main.py condiciona admin routers                         (3 matches)
✓ .env.example tiene ENABLE_ADMIN_API=false                (2 matches)
✓ Validación de API key (cambia-esto)                      (2 matches)
✓ python -m py_compile backend/app/config.py               OK
✓ python -m py_compile backend/app/main.py                 OK
```

---

## Principio de seguridad aplicado

La API ahora solo expone endpoints HMI + WebSocket + Health por defecto. Los endpoints administrativos (`/admin/ssh/execute`, `/admin/deploy/*`) y la auto-conexión SSH requieren `ENABLE_ADMIN_API=true` explícitamente, y la API key es validada en startup contra valores inseguros.
