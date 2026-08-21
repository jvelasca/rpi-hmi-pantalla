# Seguridad — Modelo de amenazas y política

> HMI de Raspberry Pi (FastAPI + Pygame + SolidJS) desplegado en una LAN de
> confianza. Este documento describe el modelo de amenazas asumido y la
> política de seguridad explícita del backend.
>
> Última revisión: 2026-08-20 · Versión del proyecto: 0.3.2

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
| **PUBLIC** | `GET /health`, `GET /health/live`, `GET /health/ready`, `GET /api/auth/status` | Ninguna |
| **AUTH** | `POST /api/auth/login`, `POST /api/auth/logout` | `POST /api/auth/login` valida `ADMIN_API_KEY` (body JSON) y emite cookie de sesión; `logout` revoca la sesión |
| **LOCAL (HMI, solo lectura/visual)** | `GET /api/status`, `GET /api/led`, `GET /api/button`, `GET /api/display/info`, `GET /api/settings/display`, `GET /api/network` | Ninguna (LAN de confianza) |
| **PROTECTED** | `POST /api/led/toggle`, `POST /api/led/on`, `POST /api/led/off`, `POST /api/button/press`, `POST /api/button/release`, `POST /api/display/command`, `POST /api/settings/display`, `WS /ws` (clientes no-loopback), `POST /api/network/static`, `POST /api/network/dhcp` | `X-API-Key` **o** cookie de sesión, **solo si** `SECURITY_MODE=protected` (loopback exento) |
| **ADMIN** | `POST /admin/ssh/connect`, `POST /admin/ssh/disconnect`, `GET /admin/ssh/status`, `POST /admin/ssh/execute`, `GET /admin/deploy/scan`, `POST /admin/deploy/setup`, `POST /admin/deploy/app`, `GET /admin/deploy/diagnostics`, `GET /admin/deploy/health`, `POST /admin/deploy/start`, `POST /admin/deploy/stop` | `X-API-Key` **o** cookie de sesión, **siempre**; solo existen si `ENABLE_ADMIN_API=true` |

Notas:

- Los routers `/admin/*` solo se registran cuando `ENABLE_ADMIN_API=true`
  (deshabilitada por defecto). Si está deshabilitada, las rutas `/admin/*`
  no existen (responden 404).
- Los endpoints HMI de solo lectura (`GET /api/*`, `GET /api/settings/display`)
  y `GET /api/network` son públicos a propósito.
- `POST /api/settings/display` (ajustes visuales) está en **PROTECTED**: en modo
  `protected` exige `X-API-Key` salvo desde loopback, de modo que el display
  local (Pygame) sigue ajustando fuente/tamaño sin key.
- `GET /api/network` es público a propósito (solo lectura); los `POST` que mutan
  la red son los que exigen auth en modo `protected`.
- `POST /api/auth/login` aplica **rate-limiting** anti brute-force: ventana fija
  en memoria por IP de cliente, contando solo intentos fallidos. Superado
  `LOGIN_MAX_ATTEMPTS` dentro de `LOGIN_WINDOW_SECONDS` responde **429**; un login
  correcto reinicia el contador de esa IP (ver §3).

### Exención de loopback (REST + WS)

El display físico (Pygame) se conecta a `localhost:8000` (REST y `ws://`) desde la
propia Pi. En `SECURITY_MODE=protected`, las peticiones cuyo host de cliente sea
`127.0.0.1`, `::1` o `localhost` se aceptan **sin** `X-API-Key` (display local de
confianza). Aplica a:

- **REST**: la dependencia `require_admin_api_key` (ver `backend/app/api/deps.py`)
  exime a loopback, de modo que los mutadores HMI (`/api/led/*`, `/api/button/*`,
  `/api/settings/display`, etc.) siguen funcionando desde el display local.
- **WS**: el handshake `WS /ws` exime a loopback.

El resto de clientes deben autenticarse con `ADMIN_API_KEY` **o** con una
cookie de sesión válida:

- **Navegador (panel web)**: inicia sesión en `POST /api/auth/login` con la
  `ADMIN_API_KEY` en el body JSON. El backend responde con una cookie de sesión
  `HttpOnly; SameSite=Strict` (nombre `rpi_hmi_session`). A partir de ahí, el
  navegador envía la cookie automáticamente en REST (fetch) y WS (handshake),
  sin que la clave llegue nunca al JS del bundle. `POST /api/auth/logout`
  revoca la sesión.
- **Scripts / M2M**: header `X-API-Key` en REST; en WS, header `X-API-Key`,
  subprotocolo `Sec-WebSocket-Protocol` (p. ej. `new WebSocket(url, ["rpi-hmi", apiKey])`)
  o query param `?token=`. Si no se autentica, el handshake se rechaza con
  close code `4401` (no se llama a `accept()`).

### Modelo de sesión (cookie HttpOnly)

- La sesión es **en memoria** (dict `token -> expiración`); se pierde al
  reiniciar el backend. El TTL se configura con `SESSION_TTL_SECONDS`
  (default `28800` = 8 h).
- El token está **firmado con HMAC-SHA256** (stdlib `hmac` + `secrets`), con
  una clave derivada de `ADMIN_API_KEY` y un secreto aleatorio por arranque.
  Así, reiniciar el proceso o rotar `ADMIN_API_KEY` invalida todas las sesiones.
- La cookie se emite con `HttpOnly` (el JS no puede leerla) y `SameSite=Strict`.
  `Secure` se activa **solo** si el backend recibe HTTPS. En la LAN de
  confianza sin TLS la cookie viaja en claro (limitación documentada); no
  expongas el puerto 8000 a Internet.

---

## 3. Variables de configuración

- **`SECURITY_MODE`** — `local` | `protected` (default **`local`**):
  - `local`: HMI de prototipo doméstico. Ningún endpoint exige `X-API-Key`.
  - `protected`: los endpoints **PROTECTED** (que mutan hardware/red) y `WS /ws`
    (para clientes no-loopback) exigen el header `X-API-Key` igual a
    `ADMIN_API_KEY`. Usa el comparador `secrets.compare_digest`
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
- **`SESSION_TTL_SECONDS`** — `int` (default **`28800`**): TTL en segundos de la
  cookie de sesión del panel web (emitida por `POST /api/auth/login`).
- **`LOGIN_MAX_ATTEMPTS`** — `int` (default **`5`**, `ge=1`): intentos fallidos de
  login permitidos por IP dentro de la ventana antes de devolver `429`.
- **`LOGIN_WINDOW_SECONDS`** — `int` (default **`300`**, `ge=10`): duración en
  segundos de la ventana fija del rate-limit de login (por IP de cliente).

Dependencias de auth (ver `backend/app/api/deps.py`):

- `require_admin_api_key` — respeta `SECURITY_MODE` (en `local` no exige nada; en
  `protected` exige `X-API-Key` **o** cookie de sesión, salvo desde loopback).
  Se usa en los mutadores HMI y de red.
- `require_admin_api_key_always` — exige `X-API-Key` **o** cookie de sesión
  **siempre**; si `ADMIN_API_KEY` está vacía devuelve `503`. Se usa en `/admin/*`.

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
- [ ] Rate-limit de login configurado (`LOGIN_MAX_ATTEMPTS` / `LOGIN_WINDOW_SECONDS`)
- [ ] Regla sudoers instalada y validada (`visudo -c`)
- [ ] Puerto 8000 no expuesto a Internet

---

## 8. Despliegue real en la Pi (2026-08-20)

Hallazgos y decisiones aplicados durante la primera instalación física (H6).

### Reducción de superficie de privilegios: sin `/dev/mem`

El LED es **virtual** (`pin: null` en `backend/config/devices.yaml`), por lo que el
backend no necesita acceso a memoria física. En `config/systemd/rpi-hmi-backend.service`
se retiró `/dev/mem` de `ReadWritePaths`, quedando:

```ini
ReadWritePaths=/home/pi/rpi_hmi/data /home/pi/rpi_hmi/backend/config /dev/gpiomem /sys/class/gpio
```

`/dev/gpiomem` se conserva para el acceso a GPIO real cuando se configure un actuador
físico. Si en el futuro se mapea un LED a un pin GPIO, las librerías (`gpiozero`/
`libgpiod`) usan `/dev/gpiomem` y **no** requieren `/dev/mem`.

### `SupplementaryGroups` separado por espacios

`systemd-analyze verify` rechaza los grupos separados por comas (regla estricta de
nombres de usuario/grupo). La unidad de display usa `SupplementaryGroups=video input
render` (espacios, no comas).

### Fin de línea LF en config Linux (CRLF → LF)

Los ficheros `systemd`, `sudoers` y `*.sh` desplegados vía SFTP desde Windows deben
llevar fin de línea LF. El archivo `.gitattributes` fuerza `eol=lf` para ellos, evitando
errores de `visudo -c` y `systemd-analyze verify` provocados por el carácter `\r` (CRLF).

### `SECURITY_MODE` en la primera instalación

La Pi quedó desplegada con `SECURITY_MODE=local` (prototipo doméstico en LAN de
confianza). La exención de loopback se extiende a REST **y** WS, por lo que
`SECURITY_MODE=protected` es compatible con el HMI táctil: el display local (loopback)
muta LED/button/display sin credenciales, mientras el resto de la LAN debe autenticarse.
Para activarlo en producción, establece `SECURITY_MODE=protected` y una `ADMIN_API_KEY`
segura (32+ caracteres) en el `.env` del backend. El panel web pedirá esa clave al
entrar (`POST /api/auth/login`) y operará con una cookie de sesión HttpOnly; los
scripts/M2M usan `X-API-Key`. Ya no es necesario (ni recomendable) compilar el
frontend con `VITE_API_KEY`.
