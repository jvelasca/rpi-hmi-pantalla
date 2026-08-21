# Runbook HIL — Validación en hardware real (v0.4.0)

> Manual operativo para ejecutar la **pasada completa de validación HIL
> (Hardware-In-the-Loop)** de la versión `0.4.0` sobre la Raspberry Pi física.
> Complementa a `docs/deploy/runbook.md` (despliegue y smoke general) y materializa
> los pendientes HIL listados en `docs/deploy/handoffs/FASE8_F6_CIERRE.md`:
> apagado brusco, SQLite corrupta, touch, DRM, login/logout y validación del
> display físico.
>
> **Alcance:** Pi 1 Model B+ (ARMv6), Bookworm, overlay `piscreen,drm` + `ads7846`,
> TFT SPI ILI9486 480x320, display por Pygame DRM/KMS, panel web SolidJS servido por
> FastAPI en `:8000`. Modo de seguridad desplegado: `SECURITY_MODE=local` (LAN de
> confianza; protección del panel **desactivada por defecto**, activable desde la UI).
>
> **Este documento es el qué ejecutar en la Pi.** No cubre la instalación base del
> sistema operativo ni el overlay DTO (ver `docs/deploy/runbook.md`).

### Registro de ejecución — (fecha / operador)

| Bloque | Resultado | Observaciones |
|---|---|---|
| 0. Prerrequisitos | ⬜ | — |
| 1. Conectividad y smoke | ⬜ | — |
| 2. Tests HIL automatizados | ⬜ | — |
| 3. Pruebas manuales | ⬜ | — |
| 4.1 SQLite corrupta (fail-closed) | ⬜ | — |
| 4.2 Apagado brusco (físico) | ⬜ | — |
| 5. Criterios de aceptación | ⬜ | — |

---

## 0. Prerrequisitos

Antes de empezar, confirma los siguientes puntos. Todos deben dar **OK** para
considerar el entorno HIL válido.

| # | Prerequisito | Verificación | Esperado |
|---|---|---|---|
| 0.1 | Pi accesible en la LAN | `ping -c 4 192.168.88.211` | 4/4 paquetes, 0% pérdida |
| 0.2 | Acceso SSH (usuario `pi`) | `ssh pi@192.168.88.211 'echo ok'` | `ok` sin pedir password interactivo |
| 0.3 | Backend activo | `ssh pi@192.168.88.211 'systemctl is-active rpi-hmi-backend.service'` | `active` |
| 0.4 | Display activo | `ssh pi@192.168.88.211 'systemctl is-active rpi-hmi-display.service'` | `active` |
| 0.5 | Versión desplegada | `ssh pi@192.168.88.211 'cat /home/pi/rpi_hmi/VERSION'` | `0.4.0` |
| 0.6 | Servicios habilitados al boot | `ssh pi@192.168.88.211 'systemctl is-enabled rpi-hmi-backend.service rpi-hmi-display.service'` | `enabled` (x2) |

```bash
# Desde el PC de desarrollo
ping -c 4 192.168.88.211
ssh pi@192.168.88.211 'echo ok'
ssh pi@192.168.88.211 'cat /home/pi/rpi_hmi/VERSION'
ssh pi@192.168.88.211 'systemctl is-active rpi-hmi-backend.service rpi-hmi-display.service'
ssh pi@192.168.88.211 'systemctl is-enabled rpi-hmi-backend.service rpi-hmi-display.service'
```

> **Nota (watchdog):** el backend corre con `Type=notify` + `WatchdogSec=30`. En
> un entorno sano `systemctl status` debe mostrar `Active: active (running)` y,
> tras varios minutos, `NRestarts=0` (sin falsos reinicios).

---

## 1. Conectividad y smoke

Verifica la ruta completa de red y el estado HTTP/JSON. Ejecuta desde la propia
Pi (vía SSH) para no depender de la LAN:

```bash
ssh pi@192.168.88.211

# 1.1 Liveness / readiness (públicos)
curl -fsS -o /dev/null -w 'health        %{http_code}\n' http://localhost:8000/health
curl -fsS -o /dev/null -w 'health/ready  %{http_code}\n' http://localhost:8000/health/ready

# 1.2 Estado (público, sin key). Debe incluir la clave "led".
curl -fsS http://localhost:8000/api/status
```

Resultado esperado:

| Endpoint | Esperado |
|---|---|
| `GET /health` | HTTP `200` |
| `GET /health/ready` | HTTP `200` |
| `GET /api/status` | HTTP `200` + JSON con clave `"led"` |

Si `health/ready` no responde `200`, el backend no está listo (posible fallo de
arranque, p. ej. SQLite no inicializada — ver §4.1). Revisa el journal:

```bash
ssh pi@192.168.88.211 'sudo journalctl -u rpi-hmi-backend.service -n 50 --no-pager'
```

---

## 2. Tests HIL automatizados

### 2.1 Tests HIL existentes

En la Pi, con el backend en marcha:

```bash
ssh pi@192.168.88.211
cd /home/pi/rpi_hmi
RPI_HIL=1 /home/pi/rpi_hmi/venv/bin/python3 -m pytest backend/tests/test_hil_hardware.py -q
```

Se esperan **5 passed**. Cada test verifica primero que el recurso de hardware
existe y se salta (`skip`) si no está presente; un `skip` inesperado indica que
el recurso concreto no está disponible y debe investigarse.

| Test | Qué valida | Recurso real |
|---|---|---|
| `test_gpiomem_exists` | GPIO accesible | `/dev/gpiomem` |
| `test_drm_card0_exists` | Display DRM presente | `/dev/dri/card0` |
| `test_backend_health_endpoint` | `/health` → 200 | Backend `:8000` |
| `test_api_status_endpoint` | `/api/status` → 200 + `"led"` | Backend `:8000` |
| `test_touch_device_present` | Touch reconocido | `/dev/input/eventN` (ADS7846/XPT2046) |

> Si aparece `1 skipped` en `test_touch_device_present`, confirma que el overlay
> `ads7846` está cargado y que el dispositivo se llama `ads7846`/`xpt2046` en
> `/sys/class/input/event*/device/name` (ver §3.1).

### 2.2 Escenarios nuevos (en ampliación, patrón a seguir)

Los escenarios HIL de login/logout, SQLite fail-closed e integridad de arranque
se están **ampliando en paralelo** como tests adicionales bajo el mismo módulo o
ficheros hermanos en `backend/tests/`. Mientras no estén fusionados, valida esos
comportamientos con las pruebas manuales/destructivas de §3 y §4.

**Patrón general de un test HIL** (consistente con `test_hil_hardware.py`):

1. Marca `@pytest.mark.hardware` + auto-skip salvo `RPI_HIL=1`:

```python
HARDWARE_AVAILABLE = os.environ.get("RPI_HIL") == "1"
pytestmark = [
    pytest.mark.hardware,
    pytest.mark.skipif(not HARDWARE_AVAILABLE, reason="HIL: requiere Raspberry Pi fisica (RPI_HIL=1)"),
]
```

2. Comprueba el recurso antes de operar y **salta** (no falla) si no existe.
3. Apunta siempre a `http://localhost:8000` (loopback, sin cruzar la LAN).
4. Usa `urllib.request` (stdlib) y `timeout` explícito, con `pytest.skip` para
   errores de conexión (`URLError`/`OSError`) y `pytest.fail` para respuestas
   inesperadas del backend.

Cuando exista un test nuevo (p. ej. `test_login_logout`), ejecútalo igual que el
resto:

```bash
RPI_HIL=1 /home/pi/rpi_hmi/venv/bin/python3 -m pytest backend/tests/test_hil_hardware.py -q
# o, si vive en su propio fichero:
RPI_HIL=1 /home/pi/rpi_hmi/venv/bin/python3 -m pytest backend/tests/test_hil_*.py -q
```

---

## 3. Pruebas manuales

### 3.1 Touch (`/dev/input/event0` ADS7846)

Verifica que el controlador táctil está presente y responde:

```bash
ssh pi@192.168.88.211
ls -l /dev/input/event*
cat /sys/class/input/event0/device/name   # debe contener ads7846 / xpt2046 / touch
```

- En la TFT, pulsa los botones de la UI. El LED virtual debe alternar al tocar
  "TOGGLE LED" y el contador de botón debe incrementarse.
- Si las coordenadas están **invertidas o desplazadas**, ajusta `invert_x`/
  `invert_y` (y `rotate`) en `display/ui/touch.py`, redeploya y repite.

### 3.2 DRM (`/dev/dri/card0`, `piscreen`)

```bash
ssh pi@192.168.88.211
ls -l /dev/dri/card0 /dev/fb1
cat /proc/device-tree/hat/product 2>/dev/null || true   # informativo
dmesg | grep -i -E 'drm|ili9486|piscreen' | tail -n 20
```

- `/dev/dri/card0` presente y `/dev/fb1` en `480x320` (resolución del TFT).
- El display Pygame corre con `SDL_VIDEODRIVER=kmsdrm` y `SDL_KMSDRM_DEVICE_INDEX=0`
  (ver la unidad `rpi-hmi-display.service`).

### 3.3 Display físico

```bash
ssh pi@192.168.88.211
systemctl status rpi-hmi-backend.service --no-pager
systemctl status rpi-hmi-display.service --no-pager
systemctl is-enabled lightdm   # debe imprimir "disabled" (o "masked")
```

- `rpi-hmi-backend.service`: `Active: active (running)`.
- `rpi-hmi-display.service`: `Active: active (running)`, sin errores DRM en el journal.
- `lightdm` **deshabilitado** (no interfiere con `/dev/dri/card0`).
- En la TFT debe verse la UI HMI (cabecera, indicador LED, botón y barra de estado).
- Confirma que el display arranca **solo al encender** la Pi (boot sin intervención).

### 3.4 Login/logout en el panel web

El panel web se sirve en `http://192.168.88.211:8000/`. En `SECURITY_MODE=local` la
protección del panel está **desactivada por defecto**, por lo que primero hay que
activarla para poder ejercitar el flujo login/logout.

**Paso A — Activar la protección (solo la primera vez):**

1. Abre `http://192.168.88.211:8000/` en el navegador.
2. Ve a Configuración → Contraseña y **cambia la de fábrica `1234`** por una nueva.
   Esto activa la protección del panel (persistida en SQLite).
3. Verifica el estado:

```bash
curl -s http://192.168.88.211:8000/api/auth/status
# Esperado: {"security_enabled": true, "authenticated": false}
```

**Paso B — Flujo por navegador:**

- [ ] Login con contraseña **incorrecta** → error (no entra, contador de rate-limit sube).
- [ ] Login con contraseña **correcta** → entra; los controles (LED/botón) quedan operativos.
- [ ] Logout → vuelve a pedir login; los controles quedan read-only.
- [ ] Tras logout, un mutador REST sin cookie/key debe rechazarse.

**Paso C — Flujo por `curl` (equivalente programático):**

```bash
# Estado de auth
curl -s http://192.168.88.211:8000/api/auth/status

# Login correcto -> 200 {"authenticated": true} + Set-Cookie HttpOnly
curl -i -c /tmp/hil_cookies.txt -X POST http://192.168.88.211:8000/api/auth/login \
  -H "Content-Type: application/json" -d '{"password":"<TU_CONTRASENA>"}'

# Login incorrecto -> 401 {"detail": "Contraseña inválida"}
curl -s -o /dev/null -w '%{http_code}\n' -X POST http://192.168.88.211:8000/api/auth/login \
  -H "Content-Type: application/json" -d '{"password":"incorrecta"}'

# Mutador con cookie de sesion -> 200
curl -s -o /dev/null -w '%{http_code}\n' -b /tmp/hil_cookies.txt \
  -X POST http://192.168.88.211:8000/api/led/toggle

# Logout -> 200 {"authenticated": false} + cookie borrada
curl -i -b /tmp/hil_cookies.txt -X POST http://192.168.88.211:8000/api/auth/logout

# Mutador SIN cookie tras logout -> 401
curl -s -o /dev/null -w '%{http_code}\n' -X POST http://192.168.88.211:8000/api/led/toggle
```

Resultado esperado: `status` con `authenticated:false` → login `200` → mutador con
cookie `200` → logout `200` → mutador sin cookie `401`.

> **Nota:** el display local (Pygame) se conecta por loopback (`127.0.0.1`) y queda
> exento de la clave en WebSocket; si tras activar la protección el touch deja de
> mutar el LED, revisa la exención de loopback (decisión n.º 4 de `ESTADO_DESPLEGUE.md`).

---

## 4. Pruebas destructivas (con backup/rollback)

> **Precaución:** estas pruebas alteran el estado real de la Pi. Ejecuta siempre el
> backup previo indicado y ten a mano el rollback de §5.

### 4.1 SQLite corrupta → fail-closed → restauración

El comportamiento objetivo (Fase 8 / F3): si SQLite no está disponible al arrancar,
el backend **no entra en READY** (`logger.critical` + `raise`) y `systemd` reinicia,
evitando arrancar **desprotegido** (fail-open).

**Ruta de la BD:** `/home/pi/rpi_hmi/data/state.db` (`DB_PATH` default `data/state.db`,
directorio en `ReadWritePaths` del backend).

```bash
ssh pi@192.168.88.211

# 4.1.1 Backup previo
sudo systemctl stop rpi-hmi-backend.service
cp /home/pi/rpi_hmi/data/state.db /home/pi/rpi_hmi/data/state.db.hil.bak

# 4.1.2 Corromper la BD (contenido no-SQLite)
printf 'esto no es sqlite\n' > /home/pi/rpi_hmi/data/state.db

# 4.1.3 Arrancar y verificar fail-closed
sudo systemctl start rpi-hmi-backend.service
sleep 8
systemctl is-active rpi-hmi-backend.service    # esperado: activating / failed / restarts
curl -s -o /dev/null -w 'health/ready %{http_code}\n' http://localhost:8000/health/ready

# 4.1.4 Confirmar el motivo en el journal (fail-closed, no desprotegido)
sudo journalctl -u rpi-hmi-backend.service -n 40 --no-pager | grep -i 'SQLite es esencial'
```

Resultado esperado (fail-closed):

- `health/ready` **no** devuelve `200` (el backend no entra en READY).
- El journal muestra el mensaje crítico `SQLite es esencial: ... El backend NO entrara
  en READY ...` y `systemd` reinicia el servicio (`Restart=on-failure`).
- **Nunca** se observa un backend respondiendo `200` con seguridad desactivada.

**Restauración y verificación final:**

```bash
ssh pi@192.168.88.211
sudo systemctl stop rpi-hmi-backend.service
cp /home/pi/rpi_hmi/data/state.db.hil.bak /home/pi/rpi_hmi/data/state.db
sudo systemctl start rpi-hmi-backend.service
sleep 5
curl -fsS -o /dev/null -w 'health/ready %{http_code}\n' http://localhost:8000/health/ready
curl -fsS http://localhost:8000/api/status
sudo systemctl restart rpi-hmi-display.service   # reengancha el display al backend
```

Esperado tras restaurar: `health/ready 200`, `/api/status` con `"led"`, display UI
visible en la TFT, y `systemctl is-active rpi-hmi-backend.service` = `active`.

### 4.2 Apagado brusco (acción física — no se automatiza)

Esta prueba **requiere acción física del usuario** (cortar alimentación). No puede
automatizarse por SSH: un `sudo reboot`/`shutdown` es un apagado limpio y no ejercita
el caso. Documenta aquí el procedimiento exacto y ejecútalo presencialmente.

**Procedimiento:**

1. **Preparar el estado conocido:** con la UI (o `curl`) deja el LED en un estado
   determinista, p. ej. **encendido**, para poder verificar la restauración posterior
   (`STARTUP_POLICY=restore`).
2. **Cortar alimentación bruscamente:** desconecta el cable de alimentación de la Pi
   **sin** apagar por software. No uses `shutdown`, `reboot` ni `poweroff`.
3. **Esperar ~5 s** con la Pi sin corriente (asegúrate de que los LEDs de estado se
   apagan por completo).
4. **Reconectar alimentación** y esperar el arranque completo (30–60 s en ARMv6).
5. **Verificar boot y servicios:**

```bash
ping -c 4 192.168.88.211
ssh pi@192.168.88.211 'systemctl is-active rpi-hmi-backend.service rpi-hmi-display.service'
ssh pi@192.168.88.211 'systemctl show rpi-hmi-backend.service -p NRestarts'
```

6. **Verificar integridad SQLite** tras el corte (no debe quedar corrupta):

```bash
ssh pi@192.168.88.211 '/home/pi/rpi_hmi/venv/bin/python3 -c "import sqlite3; print(sqlite3.connect(\"/home/pi/rpi_hmi/data/state.db\").execute(\"PRAGMA integrity_check\").fetchone()[0])"'
```

7. **Verificar restauración del estado:** en la UI o `/api/status`, confirma que el LED
   volvió al estado dejado en el paso 1 (política `restore`).
8. **Verificar watchdog:** `NRestarts=0` tras el boot (sin falsos reinicios).

Resultado esperado: Pi arranca sola, ambos servicios `active`, `NRestarts=0`,
`PRAGMA integrity_check` = `ok`, LED restaurado y display UI visible en la TFT.

---

## 5. Criterios de aceptación y rollback

### 5.1 Criterios de aceptación (gate HIL 0.4.0)

| # | Criterio | Método | Aprobado |
|---|---|---|---|
| A1 | Pi alcanzable en `192.168.88.211` por ping y SSH | §0, §1 | ⬜ |
| A2 | `rpi-hmi-backend.service` y `rpi-hmi-display.service` `active` y `enabled` | §0 | ⬜ |
| A3 | Versión `0.4.0` desplegada (`VERSION` y `/api/status`) | §0 | ⬜ |
| A4 | `/health` y `/health/ready` → 200; `/api/status` → JSON con `"led"` | §1 | ⬜ |
| A5 | Tests HIL existentes: 5 passed | §2.1 | ⬜ |
| A6 | Touch responde en `/dev/input/event0` con coordenadas correctas | §3.1 | ⬜ |
| A7 | DRM `/dev/dri/card0` + `piscreen` presente; TFT 480x320 | §3.2 | ⬜ |
| A8 | Display físico: servicios vivos, `lightdm` deshabilitado, UI visible en la TFT | §3.3 | ⬜ |
| A9 | Login/logout del panel web correctos (login 200, logout revoca sesión, mutador sin sesión → 401) | §3.4 | ⬜ |
| A10 | SQLite corrupta → fail-closed (no entra READY) y restauración limpia | §4.1 | ⬜ |
| A11 | Apagado brusco → boot autónomo, integridad SQLite `ok`, LED restaurado, `NRestarts=0` | §4.2 | ⬜ |

**Cierre:** el gate HIL se da por **aprobado** solo si A1–A11 están todos en ✅.
Cualquier ❌ se registra en la tabla de §6 con la acción de seguimiento.

### 5.2 Rollback

Si una prueba destructiva deja el sistema en mal estado, revierte en este orden:

1. **SQLite:** restaura el backup (§4.1) y reinicia el backend:

```bash
ssh pi@192.168.88.211
sudo systemctl stop rpi-hmi-backend.service
cp /home/pi/rpi_hmi/data/state.db.hil.bak /home/pi/rpi_hmi/data/state.db
sudo systemctl start rpi-hmi-backend.service
```

2. **Servicios:** reinicia el stack completo:

```bash
ssh pi@192.168.88.211 'sudo systemctl restart rpi-hmi-backend.service rpi-hmi-display.service'
```

3. **Versión/despliegue:** si hay que volver a una release anterior, usa el despliegue
   atómico (ver `docs/deploy/runbook.md` §5):

```bash
python scripts/deploy_atomic.py --list     # releases instalados
python scripts/deploy_atomic.py --rollback # vuelve a la release previa a current
```

4. **Estado de seguridad:** si la protección del panel quedó activada y se desea
   revertir a `local` sin auth, desactívala desde la UI (Configuración → Contraseña)
   o restaura la BD del backup.

---

## 6. Registro de resultados

| Bloque | Resultado (✅/❌/⬜) | Notas / evidencias |
|---|---|---|
| 0. Prerrequisitos | ⬜ | |
| 1. Conectividad y smoke | ⬜ | |
| 2.1 Tests HIL existentes (5) | ⬜ | |
| 2.2 Escenarios nuevos | ⬜ | (en ampliación; ver §2.2) |
| 3.1 Touch | ⬜ | |
| 3.2 DRM | ⬜ | |
| 3.3 Display físico | ⬜ | |
| 3.4 Login/logout | ⬜ | |
| 4.1 SQLite fail-closed | ⬜ | |
| 4.2 Apagado brusco | ⬜ | |

---

## 7. Referencias

- `docs/deploy/runbook.md` — despliegue, systemd, smoke y rollback generales.
- `docs/deploy/ESTADO_DESPLEGUE.md` — estado global, decisiones (n.º 4 loopback WS,
  n.º 17 `SECURITY_MODE=local`, n.º 18 sin `/dev/mem`).
- `docs/deploy/handoffs/FASE8_F6_CIERRE.md` — cierre 0.4.0 y pendientes HIL.
- `docs/deploy/handoffs/FASE8_F3_FAIL_CLOSED.md` — comportamiento fail-closed de SQLite.
- `backend/tests/test_hil_hardware.py` — tests HIL existentes y patrón a seguir.
- `backend/app/api/auth.py` — endpoints `/api/auth/login`, `/logout`, `/status`.
- `backend/app/services/persistence.py` — persistencia SQLite (`data/state.db`).
- `config/systemd/rpi-hmi-backend.service` y `rpi-hmi-display.service` — unidades systemd.
- `docs/CONTEXT.md` — estado global y overlay actual (`piscreen,drm` + `ads7846`).
