# Seguridad — Modelo de amenazas y política

> HMI de Raspberry Pi (FastAPI + Pygame + SolidJS) desplegado en una LAN de
> confianza. Este documento describe el modelo de amenazas asumido y la
> política de seguridad explícita del backend.
>
> Última revisión: 2026-08-20 · Versión del proyecto: 0.3.0

## 1. Modelo de amenazas

### Supuestos de despliegue

- El backend escucha en `0.0.0.0:8000` dentro de una **LAN de confianza**
  (casa / laboratorio). No hay TLS ni autenticación de usuario.
- No está diseñado para exponerse directamente a Internet.

### Activos a proteger

| Activo | Riesgo si se compromete |
|---|---|
| Estado del hardware (LED virtual y, si se configura, GPIO físico) | Manipulación del HMI |
| Configuración de red de la Pi (`nmcli`) | Pérdida de acceso (IP rota) |
| Acceso SSH remoto y despliegue (`/admin/*`) | Control total de la Pi |

### Amenazas principales

- **Manipulación del estado HMI** por un host de la misma LAN (endpoints LOCAL sin auth).
- **Cambio no autorizado de la red** (endpoints PROTECTED) que deje la Pi inaccesible.
- **Ejecución remota de comandos (RCE)** vía `/admin/ssh/execute` si la API key se filtra.

---

## 2. Clasificación de endpoints

| Clase | Endpoints | Autenticación |
|---|---|---|
| **PUBLIC** | `GET /health`, `GET /health/live`, `GET /health/ready` | Ninguna |
| **LOCAL (HMI)** | `GET /api/status`, `GET /api/led`, `POST /api/led/toggle`, `POST /api/led/on`, `POST /api/led/off`, `GET /api/button`, `POST /api/button/press`, `POST /api/button/release`, `WS /ws`, `GET /api/network` | Ninguna (LAN de confianza) |
| **PROTECTED** | `POST /api/network/static`, `POST /api/network/dhcp` | `X-API-Key` **solo si** `SECURITY_MODE=protected` |
| **ADMIN** | `POST /admin/ssh/connect`, `POST /admin/ssh/disconnect`, `GET /admin/ssh/status`, `POST /admin/ssh/execute`, `GET /admin/deploy/scan`, `POST /admin/deploy/setup`, `POST /admin/deploy/app`, `GET /admin/deploy/diagnostics`, `GET /admin/deploy/health`, `POST /admin/deploy/start`, `POST /admin/deploy/stop` | `X-API-Key` **siempre**; solo existen si `ENABLE_ADMIN_API=true` |

Notas:

- Los routers `/admin/*` solo se registran cuando `ENABLE_ADMIN_API=true`
  (deshabilitada por defecto). Si está deshabilitada, las rutas `/admin/*`
  no existen (responden 404).
- Además de los listados, también son **LOCAL** (sin auth) los endpoints HMI de
  solo visualización/ajustes: `GET /api/display/info`, `GET|POST /api/settings/display`
  y `POST /api/display/command`.
- `GET /api/network` es público a propósito (solo lectura); los `POST` que mutan
  la red son los que exigen auth en modo `protected`.

---

## 3. Variables de configuración

- **`SECURITY_MODE`** — `local` | `protected` (default **`local`**):
  - `local`: HMI de prototipo doméstico. Ningún endpoint exige `X-API-Key`.
  - `protected`: los endpoints **PROTECTED** (que mutan la red) exigen el header
    `X-API-Key` igual a `ADMIN_API_KEY`. Usa el comparador `secrets.compare_digest`
    (ver `backend/app/api/deps.py`).
- **`ADMIN_API_KEY`** — clave compartida enviada como `X-API-Key`. Protege:
  - los endpoints **PROTECTED** cuando `SECURITY_MODE=protected`, y
  - los endpoints **ADMIN** (`/admin/*`) **siempre**.
  Si está vacía, `config.py` registra un `CRITICAL` al arrancar. Genera una clave
  segura con:
  ```bash
  python -c "import secrets; print(secrets.token_urlsafe(32))"
  ```
- **`ENABLE_ADMIN_API`** — `bool` (default **`false`**): habilita los routers
  `/admin/*`. Debe permanecer `false` en producción.

Ejemplo de `.env`:

```bash
SECURITY_MODE=protected
ADMIN_API_KEY=<clave-segura-de-32+-caracteres>
ENABLE_ADMIN_API=false
```

---

## 4. Advertencia: RCE remoto en `POST /admin/ssh/execute`

`POST /admin/ssh/execute` ejecuta un **comando arbitrario** en la Raspberry Pi
a través de la conexión SSH gestionada por el backend. Es **RCE remoto**: si la
`ADMIN_API_KEY` se compromete (o se deja el valor por defecto), un atacante en la
LAN puede ejecutar cualquier comando en la Pi con los privilegios del usuario SSH.

Mitigaciones obligatorias:

- Mantén `ENABLE_ADMIN_API=false` en producción.
- Si debes activarla, usa una `ADMIN_API_KEY` de 32+ caracteres y rótala.
- No expongas el puerto 8000 a Internet (sin TLS ni rate-limiting).

---

## 5. Regla sudoers mínima

`NetworkService` ejecuta `sudo nmcli ...` para cambiar la configuración de red
desde un servicio `User=pi`. La regla mínima está en
`config/sudoers.d/rpi-hmi` y solo concede `nmcli` (nada de `ALL`):

```sudoers
pi ALL=(root) NOPASSWD: /usr/bin/nmcli
```

Instalación (en la Pi, como root):

```bash
sudo install -m 0440 config/sudoers.d/rpi-hmi /etc/sudoers.d/
sudo visudo -c
which nmcli   # verificar que la ruta coincide (/usr/bin/nmcli en Bookworm)
```

---

## 6. Safe-state (política de estado en arranque / fallo / apagado)

Política explícita de qué ocurre con el estado del dispositivo en cada momento.

| Momento | Comportamiento |
|---|---|
| **Arranque** | `state_manager.restore_from_db()` restaura desde SQLite (`data/state.db`) el estado del LED, el contador del botón y los ajustes de display. El pin GPIO se lee **siempre** de `backend/config/devices.yaml` (fuente única de verdad), nunca de la BD. Tras restaurar, `_apply_hardware_state()` sincroniza el GPIO físico si existe. |
| **Fallo del backend** | No hay reset a un valor "seguro": el LED **conserva su último estado**. El estado lógico ya quedó persistido en SQLite en cada cambio, por lo que al reiniciar el backend se restaura. El display (Pygame) y el frontend web mantienen su última vista conocida. |
| **Apagado limpio** | En el shutdown del lifespan: `flush_pending_tasks()` drena las escrituras de persistencia pendientes, `close_persistence()` cierra SQLite y `gpio_service.cleanup()` libera los pines GPIO configurados. |

> **Nota pragmática**: el LED es actualmente **virtual** (`pin: null`,
> `virtual: true` en `backend/config/devices.yaml`). Por tanto, "el LED conserva
> su último estado" se refiere al estado lógico (persistido y renderizado), no a
> un pin físico. Si en el futuro se mapea un LED a un GPIO real, ese pin
> conservará el último nivel de salida hasta que el backend se reinicie y
> restaure el estado desde SQLite.

---

## 7. Checklist de producción

- [ ] `ENABLE_ADMIN_API=false`
- [ ] `ADMIN_API_KEY` segura (32+ caracteres), distinta del valor por defecto
- [ ] `SECURITY_MODE` decidido explícitamente (`local` o `protected`)
- [ ] Regla sudoers instalada y validada (`visudo -c`)
- [ ] Puerto 8000 no expuesto a Internet
