# Seguridad — Modelo de amenazas y política

> HMI de Raspberry Pi (FastAPI + Pygame + SolidJS) desplegado en una LAN de
> confianza. Este documento describe el modelo de amenazas asumido y la
> política de seguridad explícita del backend.
>
> Última revisión: 2026-08-21 · Versión del proyecto: 0.4.1

## 1. Modelo de amenazas

### Supuestos de despliegue

- El backend escucha en `0.0.0.0:8000` dentro de una **LAN de confianza**
  (casa / laboratorio). No hay TLS ni autenticación de usuario.
- No está diseñado para exponerse directamente a Internet.

### Activos a proteger

| Activo | Riesgo si se compromete |
|---|---|
| Estado del hardware (LED físico en GPIO20/21) | Manipulación del HMI |
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
| **AUTH** | `POST /api/auth/login`, `POST /api/auth/logout` | `POST /api/auth/login` valida la **contraseña del panel** (body JSON) y emite cookie de sesión; `logout` revoca la sesión |
| **SECURITY** | `GET /api/auth/security`, `POST /api/auth/security`, `POST /api/auth/password` | `GET` es público; los `POST` exigen cookie de sesión, `X-API-Key` o la contraseña actual (`current`) |
| **LOCAL (HMI, solo lectura/visual)** | `GET /api/status`, `GET /api/led`, `GET /api/button`, `GET /api/display/info`, `GET /api/settings/display`, `GET /api/network` | Ninguna (LAN de confianza) |
| **PROTECTED** | `POST /api/led/toggle`, `POST /api/led/on`, `POST /api/led/off`, `POST /api/button/press`, `POST /api/button/release`, `POST /api/display/command`, `POST /api/settings/display`, `WS /ws` (clientes no-loopback), `POST /api/network/static`, `POST /api/network/dhcp` | `X-API-Key` **o** cookie de sesión, **solo si** la contraseña del panel está activada (loopback exento) |
| **ADMIN** | `POST /admin/ssh/connect`, `POST /admin/ssh/disconnect`, `GET /admin/ssh/status`, `POST /admin/ssh/execute`, `GET /admin/deploy/scan`, `POST /admin/deploy/setup`, `POST /admin/deploy/app`, `GET /admin/deploy/diagnostics`, `GET /admin/deploy/health`, `POST /admin/deploy/start`, `POST /admin/deploy/stop` | `X-API-Key` (ADMIN_API_KEY) **únicamente**, **siempre** (no acepta cookie de sesión); solo existen si `ENABLE_ADMIN_API=true` |

Notas:

- Los routers `/admin/*` solo se registran cuando `ENABLE_ADMIN_API=true`
  (deshabilitada por defecto). Si está deshabilitada, las rutas `/admin/*`
  no existen (responden 404).
- Los endpoints HMI de solo lectura (`GET /api/*`, `GET /api/settings/display`)
  y `GET /api/network` son públicos a propósito.
- `POST /api/settings/display` (ajustes visuales) está en **PROTECTED**: cuando
  la contraseña del panel está activada exige `X-API-Key` salvo desde loopback,
  de modo que el display local (Pygame) sigue ajustando fuente/tamaño sin key.
- `GET /api/network` es público a propósito (solo lectura); los `POST` que mutan
  la red son los que exigen auth cuando la contraseña del panel está activada.
- `POST /api/auth/login` aplica **rate-limiting** anti brute-force: ventana fija
  en memoria por IP de cliente, contando solo intentos fallidos. Superado
  `LOGIN_MAX_ATTEMPTS` dentro de `LOGIN_WINDOW_SECONDS` responde **429**; un login
  correcto reinicia el contador de esa IP (ver §3).
- Los `POST /api/auth/security` y `POST /api/auth/password` reutilizan el mismo
  rate-limiter de fallos de login, para frenar brute-force sobre los cambios de
  seguridad.

### Exención de loopback (REST + WS)

El display físico (Pygame) se conecta a `localhost:8000` (REST y `ws://`) desde la
propia Pi. Cuando la contraseña del panel está activada, las peticiones cuyo
host de cliente sea
`127.0.0.1`, `::1` o `localhost` se aceptan **sin** `X-API-Key` (display local de
confianza). Aplica a:

- **REST**: la dependencia `require_admin_api_key` (ver `backend/app/api/deps.py`)
  exime a loopback, de modo que los mutadores HMI (`/api/led/*`, `/api/button/*`,
  `/api/settings/display`, etc.) siguen funcionando desde el display local.
- **WS**: el handshake `WS /ws` exime a loopback.

El resto de clientes deben autenticarse con `ADMIN_API_KEY` **o** con una
cookie de sesión válida:

- **Navegador (panel web)**: inicia sesión en `POST /api/auth/login` con la
  **contraseña del panel** en el body JSON (por defecto `1234`, gestionable
  desde la UI). El backend responde con una cookie de sesión
  `HttpOnly; SameSite=Strict` (nombre `rpi_hmi_session`). A partir de ahí, el
  navegador envía la cookie automáticamente en REST (fetch) y WS (handshake),
  sin que la contraseña llegue nunca al JS del bundle. `POST /api/auth/logout`
  revoca la sesión.
- **Scripts / M2M**: header `X-API-Key` en REST; en WS, header `X-API-Key` o
  subprotocolo `Sec-WebSocket-Protocol` (p. ej. `new WebSocket(url, ["rpi-hmi", apiKey])`).
  El query param `?token=` **ya no** es una fuente de credencial. Si no se
  autentica, el handshake se rechaza con close code `4401` (no se llama a
  `accept()`).

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

- **Panel security (activación de la contraseña del panel)** — la protección se
  rige por el flag `password_enabled` persistido en SQLite (tabla
  `security_settings`) y leído por `security_manager.load()`. El estado por
  defecto de `security_manager.is_enabled()` es **`False`** (contraseña **OFF**
  al arrancar). La
  activación/desactivación se hace en caliente desde la UI (`/api/auth/security`)
  y persiste entre reinicios. Cuando está activada, los endpoints **PROTECTED**
  (que mutan hardware/red) y `WS /ws` (para clientes no-loopback) exigen el
  header `X-API-Key` igual a `ADMIN_API_KEY` **o** una cookie de sesión válida
  (ver §9).
- **Contraseña del panel web** — persistida en SQLite con hash PBKDF2-HMAC-SHA256
  (stdlib). Valor de fábrica `1234`. Se gestiona desde la UI (Configuración →
  Contraseña) vía `/api/auth/security` y `/api/auth/password`, sin tocar
  `ADMIN_API_KEY`. Para **activar** la protección primero hay que cambiar la
  contraseña de fábrica por una personalizada (mínimo 8 caracteres); el
  backend responde `409` si se intenta activar manteniendo `1234`.
- **`ADMIN_API_KEY`** — clave compartida M2M enviada como `X-API-Key`. Protege:
  - los endpoints **PROTECTED** cuando la contraseña del panel está activada, y
  - los endpoints **ADMIN** (`/admin/*`) **siempre**.
  Ya **no** es la credencial de login del panel web (ahora se usa la contraseña
  del panel). Si está vacía, `config.py` registra un `CRITICAL` al arrancar.
  Genera una clave segura con:
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

- `require_admin_api_key` — respeta `security_manager.is_enabled()` (si la
  contraseña del panel está desactivada no exige nada; si está activada exige
  `X-API-Key` **o** cookie de sesión, salvo desde loopback). Se usa en los
  mutadores HMI y de red.
- `require_admin_api_key_always` — exige `X-API-Key` (ADMIN_API_KEY)
  **únicamente**, **siempre** (NO acepta cookie de sesión); si `ADMIN_API_KEY`
  está vacía devuelve `503`. Se usa en `/admin/*`.

Ejemplo de `.env`:

```bash
ADMIN_API_KEY=<clave-segura-de-32+-caracteres>
ENABLE_ADMIN_API=false
# La contraseña del panel se activa desde la UI (Configuración → Contraseña),
# no con una variable de entorno.
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

> **Nota pragmática**: los LEDs son físicos (GPIO 20 para el LED principal y
> GPIO 21 para el LED del pulsador, en `backend/config/devices.yaml`). Por tanto,
> "el LED conserva su último estado" se refiere tanto al estado lógico
> (persistido y renderizado) como al nivel de salida del pin, que conserva su
> último valor hasta que el backend se reinicie y restaure el estado desde SQLite.

---

## 7. Checklist de producción

- [ ] `ENABLE_ADMIN_API=false`
- [ ] `ADMIN_API_KEY` segura (32+ caracteres), distinta del valor por defecto
- [ ] Contraseña del panel activada/desactivada explícitamente desde la UI (persistida en SQLite)
- [ ] Rate-limit de login configurado (`LOGIN_MAX_ATTEMPTS` / `LOGIN_WINDOW_SECONDS`)
- [ ] Regla sudoers instalada y validada (`visudo -c`)
- [ ] Puerto 8000 no expuesto a Internet

---

## 8. Despliegue real en la Pi (2026-08-20)

Hallazgos y decisiones aplicados durante la primera instalación física (H6).

### Reducción de superficie de privilegios: sin `/dev/mem`

Los LEDs son físicos (GPIO 20 y GPIO 21 en `backend/config/devices.yaml`). El
backend accede a GPIO vía `/dev/gpiomem`; en `config/systemd/rpi-hmi-backend.service`
se retiró `/dev/mem` de `ReadWritePaths`, quedando:

```ini
ReadWritePaths=/home/pi/rpi_hmi/data /home/pi/rpi_hmi/backend/config /dev/gpiomem /sys/class/gpio
```

`/dev/gpiomem` se conserva para el acceso a GPIO real (`gpiozero`/`libgpiod` usa
`/dev/gpiomem` y **no** requiere `/dev/mem`).

### `SupplementaryGroups` separado por espacios

`systemd-analyze verify` rechaza los grupos separados por comas (regla estricta de
nombres de usuario/grupo). La unidad de display usa `SupplementaryGroups=video input
render` (espacios, no comas).

### Fin de línea LF en config Linux (CRLF → LF)

Los ficheros `systemd`, `sudoers` y `*.sh` desplegados vía SFTP desde Windows deben
llevar fin de línea LF. El archivo `.gitattributes` fuerza `eol=lf` para ellos, evitando
errores de `visudo -c` y `systemd-analyze verify` provocados por el carácter `\r` (CRLF).

### Protección del panel en la primera instalación

La Pi quedó desplegada con la contraseña del panel **desactivada** (prototipo
doméstico en LAN de confianza). La exención de loopback se extiende a REST **y**
WS, por lo que el HMI táctil local (loopback) muta LED/button/display sin
credenciales.

Desde la FASE 7, la contraseña del panel está **desactivada por defecto** y se
persiste en SQLite (`password_enabled`). Para proteger el panel: (1) cambia la contraseña de fábrica (`1234`) por una
personalizada (mínimo 8 caracteres) y (2) actívala desde la UI (Configuración →
Contraseña). El panel web pedirá login al entrar (`POST /api/auth/login`) y
operará con una cookie de sesión HttpOnly; los scripts/M2M usan `X-API-Key`. Ya
no es necesario (ni recomendable) compilar el frontend con `VITE_API_KEY`.

---

## 9. Contraseña del panel web (persistida)

A partir de la versión 0.3.3 (FASE 6), el login del panel web **ya no usa
`ADMIN_API_KEY`**. En su lugar se introduce una **contraseña de panel** con
estado de activación propio, gestionable en caliente desde la UI y persistida
en SQLite. La contraseña está **desactivada por defecto** (la web no pide
login al cargar).

- **Contraseña de fábrica**: `1234` (se recomienda cambiarla).
- **Mínimo de la nueva contraseña**: 8 caracteres.
- **Persistencia**: tabla `security_settings` (`password_hash`,
  `password_enabled`, `updated_at`), migraciones `_migration_003` (crea y
  siembra `password_enabled=0`) y `_migration_004` (fuerza
  `password_enabled=0` en instalaciones previas).
- **Hashing**: PBKDF2-HMAC-SHA256 con salt aleatorio (120k iteraciones,
  stdlib `hashlib` + `secrets`), comparación con `hmac.compare_digest`.
  Formato: `pbkdf2_sha256$<iter>$<salt_b64>$<hash_b64>` (base64url). Ver
  `backend/app/services/password_hash.py`.
- **Runtime**: `security_manager` (singleton en
  `backend/app/services/security_manager.py`) mantiene la cache en memoria.
  `is_enabled()` parte de `False`; el estado real es `password_enabled`
  persistido en SQLite, leído por `security_manager.load()`. Se usa en
  `deps.py`, `ws.py` y `auth.py/status`.

### Endpoints

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/api/auth/security` | Estado público `{enabled, is_default}` |
| `POST` | `/api/auth/security` | Activa/desactiva (`{enabled, current?}`). Si se intenta activar con la contraseña de fábrica, responde `409` |
| `POST` | `/api/auth/password` | Cambia contraseña (`{current, new}`); `new` con mínimo 8 caracteres (si no, `422`) |

Autorización de los `POST` (helper `_authorize_security_change`): se permite si
(a) hay cookie de sesión válida, (b) `X-API-Key` coincide con `ADMIN_API_KEY`
(si está configurada) o (c) `current` verifica contra la contraseña almacenada.
`POST /api/auth/password` exige **siempre** que `current` verifique y, al éxito,
revoca todas las sesiones (`session_manager.clear()`).

Activación forzada: `POST /api/auth/security` con `enabled=true` devuelve
`409` mientras `security_manager.is_default_password()` sea cierto (es decir,
mientras la contraseña siga siendo `1234`). El usuario debe cambiar la
contraseña primero.

### `require_admin_api_key` (mutadores HMI)

El chequeo de la cookie de sesión se realiza **antes** del chequeo de
`ADMIN_API_KEY` vacía, de modo que el panel web funciona aunque `ADMIN_API_KEY`
no esté configurada (solo se exige `ADMIN_API_KEY` para el path `X-API-Key`).
`require_admin_api_key_always` (para `/admin/*`) exige `X-API-Key`
(`ADMIN_API_KEY`) **únicamente**: ya **no** acepta cookie de sesión, de modo
que una contraseña HMI de bajo privilegio nunca concede acceso administrativo.
