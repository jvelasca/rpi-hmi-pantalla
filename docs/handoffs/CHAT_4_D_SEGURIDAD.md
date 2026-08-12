# HANDOFF — Chat 4: Fase D — Hardening de Seguridad

> **Precondición:** Chats 1, 2 y 3 completados
> **Salida esperada:** `docs/handoffs/CHAT_4_D_RESULTADO.md` + texto de handoff para Chat 5
> **Duración estimada:** 30-45 min

---

## Contexto

La API tiene una superficie de ataque innecesaria para una HMI industrial:

1. **`/admin/ssh/execute`** permite ejecutar **cualquier comando** en la Raspberry Pi
   (RCE completa). Con `/admin/ssh/connect` se puede conectar a hosts arbitrarios.
2. **`/admin/deploy/*`** permite desplegar código desde la API (aunque conceptualmente roto
   por usar `Path.cwd()`). La API HMI no debería poder modificar el sistema operativo.
3. **`ADMIN_API_KEY`** tiene un valor por defecto (`cambia-esto-por-una-clave-segura`)
   que es una clave conocida.
4. La API HMI (`/api/led/*`, `/api/button/*`) es pública en la LAN.

**Filosofía:** El deploy debe hacerse desde el PC vía SSH. La API debe ser solo API HMI +
WebSocket + Health. Los endpoints administrativos deben estar deshabilitados por defecto en
producción, controlados por un feature gate explícito.

---

## TAREA 1: Añadir feature gate `ENABLE_ADMIN_API` en `config.py`

**Archivo:** `backend/app/config.py`

Añadir un nuevo campo después de la línea 60 (`enable_docs`):

```python
    # Admin API (deshabilitada por defecto en produccion)
    enable_admin_api: bool = Field(
        default=False,
        description="Habilitar endpoints administrativos /admin/* (SSH, deploy). "
                    "SOLO para desarrollo. En produccion usar deploy via SSH desde PC.",
    )
```

Colocarlo justo después de `enable_docs` (línea 60):

```60:61:backend/app/config.py
    enable_docs: bool = Field(default=False, description="Habilitar documentacion OpenAPI")

    # Logging
```

**Insertar entre `enable_docs` y `# Logging`:**

```python
    enable_docs: bool = Field(default=False, description="Habilitar documentacion OpenAPI")

    # Admin API (deshabilitada por defecto en produccion)
    enable_admin_api: bool = Field(
        default=False,
        description="Habilitar endpoints administrativos /admin/* (SSH, deploy). "
                    "SOLO para desarrollo. En produccion usar deploy via SSH desde PC.",
    )

    # Logging
```

---

## TAREA 2: Feature-gate admin routers en `main.py`

**Archivo:** `backend/app/main.py`

Líneas 181-183 actualmente incluyen los routers admin sin condición:

```181:183:backend/app/main.py
# Routers administrativos (requieren API key)
app.include_router(admin_ssh_router)
app.include_router(admin_deploy_router)
```

**Cambiar a:**

```python
# Routers administrativos (requieren API key) — solo si ENABLE_ADMIN_API=true
if settings.enable_admin_api:
    app.include_router(admin_ssh_router)
    app.include_router(admin_deploy_router)
    logger.warning(
        "ADMIN_API habilitada. Los endpoints /admin/ssh/* y /admin/deploy/* "
        "estan expuestos. Deshabilita con ENABLE_ADMIN_API=false en .env para produccion."
    )
```

---

## TAREA 3: Validar `ADMIN_API_KEY` en startup

**Archivo:** `backend/app/config.py`

Añadir un validador que emita una advertencia (o directamente rechace) claves inseguras.
Esto se puede hacer con un `@field_validator` de Pydantic v2 o con un método `model_post_init`.

Añadir después de la clase `Settings` (después de la línea 74, antes de `settings = Settings()`):

```python
    def model_post_init(self, __context: object = None) -> None:
        """Valida la configuracion tras cargar .env."""
        import logging
        _log = logging.getLogger(__name__)

        # Advertir sobre API key insegura
        if self.enable_admin_api:
            if not self.admin_api_key:
                _log.critical(
                    "ADMIN_API_KEY no configurada pero enable_admin_api=true. "
                    "Los endpoints /admin/* estan EXPUESTOS SIN PROTECCION."
                )
            elif self.admin_api_key == "cambia-esto-por-una-clave-segura":
                _log.critical(
                    "ADMIN_API_KEY tiene el valor por defecto. "
                    "ESTO ES INSEGURO. Cambiala en .env inmediatamente."
                )
            elif len(self.admin_api_key) < 16:
                _log.warning(
                    "ADMIN_API_KEY es demasiado corta (%d chars). "
                    "Usa al menos 32 caracteres aleatorios.", len(self.admin_api_key)
                )
```

---

## TAREA 4: Actualizar `.env.example`

**Archivo:** `.env.example`

Debe reflejar los nuevos settings y advertir claramente:

```
# ============================================================
# RPi HMI — Configuracion de entorno (.env)
# ============================================================
# Copia este archivo como .env y personaliza los valores.
# NUNCA subas .env al repositorio (esta en .gitignore).
# ============================================================

# --- Conexion SSH a la Raspberry Pi (para scripts de deploy desde PC) ---
RPI_HOST=192.168.88.211
RPI_USER=pi
RPI_PASSWORD=
RPI_KEY_PATH=
RPI_PORT=22

# --- Servidor HTTP ---
BACKEND_HOST=0.0.0.0
BACKEND_PORT=8000

# --- Seguridad ---
# ADMIN_API_KEY: solo necesaria si ENABLE_ADMIN_API=true (NO recomendado en produccion).
# Genera una clave aleatoria fuerte: python -c "import secrets; print(secrets.token_urlsafe(32))"
# El valor por defecto "cambia-esto-por-una-clave-segura" sera rechazado en startup.
ADMIN_API_KEY=cambia-esto-por-una-clave-segura

# --- Admin API (SOLO DESARROLLO) ---
# En produccion DEBE ser false. El deploy se hace via SSH desde el PC.
ENABLE_ADMIN_API=false

# --- CORS ---
CORS_ORIGINS=http://localhost:5173,http://localhost:8000

# --- Documentacion OpenAPI ---
ENABLE_DOCS=false

# --- Logging ---
LOG_LEVEL=info

# --- Persistencia ---
# DB_PATH=data/state.db
```

---

## TAREA 5: Añadir `ENABLE_ADMIN_API=false` al `.env` local si existe

Verifica si existe `.env` en la raíz (está en `.gitignore`). Si existe, asegúrate de que
contenga:

```
ENABLE_ADMIN_API=false
```

Si no existe, no lo crees (es un archivo local). Solo verifica.

---

## TAREA 6: Auto-conexión SSH solo si admin API habilitada

**Archivo:** `backend/app/main.py`

En el lifespan, la función `auto_connect_ssh()` se llama siempre. Debería condicionarse a
`settings.enable_admin_api`:

Busca en `main.py` la llamada a `auto_connect_ssh()` dentro de `lifespan` y condiciónala:

```python
if settings.enable_admin_api:
    await auto_connect_ssh()
```

(Si no se encuentra la llamada exacta, busca en el lifespan cómo se invoca.)

---

## VERIFICACIÓN

```bash
# 1. Config tiene el nuevo campo
grep "enable_admin_api" backend/app/config.py
# Debe mostrar el campo y el validador

# 2. Main.py condiciona los admin routers
grep "enable_admin_api" backend/app/main.py
# Debe mostrar el if que envuelve los include_router

# 3. .env.example tiene ENABLE_ADMIN_API
grep "ENABLE_ADMIN_API" .env.example
# Debe mostrar ENABLE_ADMIN_API=false

# 4. Admin API key validation
grep "cambia-esto" backend/app/config.py
# Debe mostrar el validador que advierte sobre la clave por defecto

# 5. Compilación
python -m py_compile backend/app/config.py
python -m py_compile backend/app/main.py
```

---

## AL FINALIZAR

Crea `docs/handoffs/CHAT_4_D_RESULTADO.md` con resumen de cambios y verificación.

Copia este texto de **handoff para Chat 5**:

```
[HANDOFF CHAT 4 → CHAT 5]

Chat 4 (Fase D - Hardening de Seguridad) completado.

Cambios realizados:
- config.py: añadido enable_admin_api (default false) + model_post_init que valida
  ADMIN_API_KEY (rechaza valor por defecto, advierte claves cortas)
- main.py: admin routers (ssh, deploy) ahora están condicionados a enable_admin_api
- main.py: auto_connect_ssh() solo se ejecuta si enable_admin_api=true
- .env.example: actualizado con ENABLE_ADMIN_API=false y advertencias de seguridad

Estado: Endpoints administrativos deshabilitados por defecto. API key validada en startup.
La superficie de ataque se ha reducido significativamente.

Tarea para Chat 5 (Fase E - Robustez y Refinamiento):
1. display/app.py: reducir polling REST cuando WS conectado
2. display/ui/touch.py: eliminar fallback ciego, obtener capacidades de evdev
3. backend/requirements.txt: separar runtime/display/dev
4. backend/__init__.py y backend/app/__init__.py: vaciar imports
5. frontend: añadir validación runtime de mensajes WS
6. frontend/src/App.tsx: gpio_pin: 0 como estado inicial
7. display/app.py: añadir version al subscribe WS
8. backend/app/api/health.py: simplificar _check_db duplicado

Documento de referencia: docs/handoffs/CHAT_5_E_ROBUSTEZ.md
```
