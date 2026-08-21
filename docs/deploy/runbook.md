# Runbook — Despliegue en la Raspberry Pi

> Manual operativo para llevar la V1 a la Raspberry Pi física. Complementa a
> `docs/deploy/INICIO.md` (qué se hace) y `docs/deploy/ESTADO_DESPLEGUE.md`
> (estado global de los workstreams). Este documento es el **qué ejecutar en la Pi**.
>
> **Estado:** los workstreams de código H1–H9 están completos y con CI verde en
> `main`. Este runbook cubre únicamente el paso de hardware (P0) y las pruebas
> físicas de cierre (gate D4).

### Registro de ejecución — 2026-08-20 (Pi 1 Model B+, ARMv6)

**Verificado programáticamente (SSH):**

- Sync SFTP de 94 archivos actualizados; servicios instalados y `systemd-analyze verify` OK.
- `SECURITY_MODE=local` desplegado (ver limitación de `protected` en `docs/SECURITY.md` §8).
- Backend `Type=notify` + watchdog activo; HIL 5/5 passed; smoke HTTP (200 público, 200 mutadores, 404 admin).
- sudoers `nmcli` funcional; `POST /api/network/static` inválido → `400` sin romper la red.
- Watchdog validado 240 s: `NRestarts=0`, `WatchdogTimestamp` avanza cada ~30 s, sin falsos reinicios.

**Pendiente de confirmación física (usuario, en la TFT):**

- Boot completo tras `reboot`; UI visible en la TFT; coordenadas de touch; reconexión WebSocket; pérdida de red/display sin tumbar el backend.

---

## 0. Prerrequisitos y alcance

- **Hardware:** Raspberry Pi (Bookworm 64-bit), TFT SPI ILI9486 (`piscreen`),
  touch XPT2046/ADS7846 (`ads7846`), fuente de alimentación adecuada.
- **Desde el PC de desarrollo:** Python 3.11+, `paramiko`, `python-dotenv`, y
  conectividad SSH a la Pi.
- **Qué NO cubre este documento:** la instalación base del sistema operativo ni
  el overlay DTO del panel. Asume la Pi ya arranca y es accesible por SSH.

### Modelo de seguridad (resumen)

| Variable | Valores | Efecto |
|---|---|---|
| `SECURITY_MODE` | `local` | HMI sin auth (prototipo doméstico). |
| `SECURITY_MODE` | `protected` | Los mutadores HMI (REST `POST /api/led/*`, `/api/button/*`, `/api/display/command` y comandos WebSocket no-loopback) exigen header `X-API-Key`. |
| `ENABLE_ADMIN_API` | `false` | `/admin/ssh/*` y `/admin/deploy/*` NO montados (producción). |
| `ADMIN_API_KEY` | 32+ chars | Clave para mutadores y `/admin/*`. |

En producción usa **`SECURITY_MODE=protected`**. El display local se conecta por
loopback (`127.0.0.1`) y queda exento de la clave; la UI web desde LAN y las
herramientas de línea necesitan el header `X-API-Key`.

---

## 1. Primera instalación en la Pi

### 1.1 Clonar el repositorio

```bash
ssh pi@<IP_DE_LA_PI>
mkdir -p ~/rpi_hmi
git clone https://github.com/jvelasca/rpi-hmi-pantalla.git ~/rpi_hmi/current
# Nota: el despliegue atómico usa ~/rpi_hmi/releases/<version> + current -> releases/...
```

### 1.2 Crear el venv e instalar dependencias

```bash
cd ~/rpi_hmi
python3 -m venv venv
source venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r backend/requirements.txt
python -m pip install -r display/requirements.txt
```

> `VENV_PIP` ya no existe: los scripts de despliegue usan siempre
> `{VENV_PY} -m pip` (`backend/app/...` → `scripts/deploy*.py`), que es robusto
> aunque el binario `pip3` no esté en el venv.

### 1.3 Regla sudoers mínima (para `nmcli`)

`config/sudoers.d/rpi-hmi` concede a `pi` ejecutar **únicamente** `nmcli` sin
password (necesario para `NetworkService`). Instálala como root:

```bash
sudo install -m 0440 config/sudoers.d/rpi-hmi /etc/sudoers.d/
sudo visudo -c   # debe imprimir "parsed OK" sin errores
```

Verifica la ruta real de `nmcli` con `which nmcli` (en Bookworm es `/usr/bin/nmcli`).

### 1.4 Configuración de producción (`.env`)

**NUNCA commitees `.env`.** Cópialo desde la plantilla y rellénalo en la Pi:

```bash
cp .env.example .env
```

Valores mínimos para producción:

```ini
RPI_HOST=<IP_DE_LA_PI>
SECURITY_MODE=protected
ENABLE_ADMIN_API=false
ADMIN_API_KEY=<clave-de-32+-caracteres>
STARTUP_POLICY=restore
CORS_ORIGINS=http://localhost:5173,http://localhost:8000
```

Genera la clave con:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

---

## 2. Instalación y validación de systemd

### 2.1 Instalar los servicios

Desde el PC de desarrollo (requiere `RPI_HOST` en `.env`):

```bash
python scripts/deploy.py --install-service
```

O manualmente en la Pi:

```bash
sudo cp config/systemd/rpi-hmi-backend.service /etc/systemd/system/
sudo cp config/systemd/rpi-hmi-display.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable rpi-hmi-backend.service rpi-hmi-display.service
```

### 2.2 Validar antes de arrancar

```bash
systemd-analyze verify rpi-hmi-backend.service rpi-hmi-display.service
sudo systemd-analyze security rpi-hmi-backend.service   # informativo
sudo systemctl daemon-reload
```

### 2.3 Arranque ordenado

El display depende del backend (`Requires=` + `ExecStartPre` que espera
`/health/ready`). Arranca el backend y confirma `READY=1` (Type=notify):

```bash
sudo systemctl start rpi-hmi-backend.service
sudo systemctl status rpi-hmi-backend.service --no-pager
# Debe aparecer "Active: active (running)" sin esperas de READY.
sudo systemctl start rpi-hmi-display.service
```

### 2.4 Watchdog (Type=notify + WatchdogSec=30)

El backend ya notifica `READY=1`, `WATCHDOG=1` (cada 15 s) y `STOPPING=1` vía
`backend/app/services/systemd_notify.py`. Comprueba que no haya falsos reinicios
tras unos minutos bajo carga:

```bash
sudo journalctl -u rpi-hmi-backend.service -f
```

Si ves reinicios cada 30 s, revisa que `NOTIFY_SOCKET` esté disponible y que el
event loop no esté saturado (consulta `docs/archive/deploy-handoffs/H9.md`).

### 2.5 `/dev/mem` en `ReadWritePaths` (P2-4)

El servicio backend monta `ReadWritePaths=... /dev/mem ...`. **En la Pi real**,
comprueba si `gpiozero`/`lgpio` necesita `/dev/mem` o si basta con `/dev/gpiomem`:

```bash
ls -l /dev/gpiomem /dev/mem
# Prueba de acceso sin /dev/mem:
#   con el servicio en marcha, usa /api/status y toggles del LED (virtual).
```

Si el LED es virtual (`pin: null` en `backend/config/devices.yaml`) y no hay
otros actuadores físicos, `/dev/mem` puede retirarse de `ReadWritePaths` para
reducir superficie de privilegio. Regístralo en `docs/SECURITY.md` al confirmarlo.

---

## 3. Smoke test (gate D4, parte HTTP)

Con el backend en marcha en la Pi, desde la propia Pi:

```bash
# Liveness / readiness (públicos)
curl -fsS -o /dev/null -w '%{http_code}\n' http://localhost:8000/health
curl -fsS -o /dev/null -w '%{http_code}\n' http://localhost:8000/health/ready

# Estado (público, sin key)
curl -fsS http://localhost:8000/api/status

# Mutador SIN key -> debe dar 401 (protected)
curl -s -o /dev/null -w '%{http_code}\n' -X POST http://localhost:8000/api/led/toggle

# Mutador CON key -> debe dar 200
curl -s -o /dev/null -w '%{http_code}\n' -X POST \
  -H "X-API-Key: $ADMIN_API_KEY" http://localhost:8000/api/led/toggle
```

Resultado esperado: `200`, `200`, JSON de estado, `401`, `200`.

---

## 4. Pruebas físicas (gate D4, parte HIL)

### 4.1 Tests HIL

En la Pi, con el backend en marcha:

```bash
RPI_HIL=1 python -m pytest backend/tests/test_hil_hardware.py -q
```

Se esperan **5 passed** (gpiomem, DRM card0, `/health`, `/api/status`, touch
presente). Si alguno se salta, revisa el recurso concreto (ver
`docs/archive/deploy-handoffs/H6-hil.md`).

### 4.2 Checklist manual de cierre

- [ ] Boot completo sin intervención (tras `reboot`).
- [ ] Display muestra la UI en la TFT.
- [ ] Touch responde y las coordenadas son correctas (si no: `invert_x`/`invert_y` en `display/ui/touch.py`).
- [ ] WebSocket conecta desde el display local (loopback).
- [ ] Reconexión WebSocket tras reiniciar el backend.
- [x] `POST /api/network/static` valida IP/gateway/subred incoherentes y devuelve 400 (sin romper la red).
- [x] Reinicio limpio: `sudo systemctl restart rpi-hmi-backend.service`.
- [ ] Pérdida de red (desconectar cable) no tumba el backend (watchdog no reinicia en falso).
- [ ] Pérdida de display (desconectar TFT) no tumba el backend.
- [ ] Restauración SQLite: togglear LED, `restart`, verificar que el LED se restaura según `STARTUP_POLICY`.

---

## 5. Despliegue continuo y rollback

### 5.1 Despliegue atómico (recomendado)

```bash
python scripts/deploy_atomic.py            # usa la versión de VERSION
python scripts/deploy_atomic.py --list     # releases instalados
```

Copia a `releases/<version>/`, valida estructura, instala deps, cambia el
symlink `current`, reinicia y verifica. Si algo falla, **no toca `current`**.

### 5.2 Rollback

```bash
python scripts/deploy_atomic.py --rollback
```

### 5.3 Despliegue simple

```bash
python scripts/deploy.py                   # deploy + verify
python scripts/deploy.py --verify          # solo verificar estado
```

---

## 6. Resolución de problemas

| Síntoma | Causa probable | Acción |
|---|---|---|
| `401` en mutadores desde LAN | Falta header `X-API-Key` | Añadir `-H "X-API-Key: ..."` o configurar la UI. |
| Servicio reinicia cada 30 s | Watchdog sin `WATCHDOG=1` | Revisar `NOTIFY_SOCKET` y logs (`journalctl`). |
| `pip3: command not found` en deploy | Script antiguo | Usar `deploy_atomic.py`/`deploy.py` actuales (`{VENV_PY} -m pip`). |
| Display no arranca | Backend no está `ready` | `curl localhost:8000/health/ready`; revisar `ExecStartPre`. |
| Touch invertido | Ejes mal mapeados | `invert_x`/`invert_y` en `display/ui/touch.py`. |
| `/dev/mem` denegado | Hardening | Ver §2.5; retirar si el LED es virtual. |

---

## 7. Referencias

- `docs/deploy/INICIO.md` — punto de arranque y mapa de workstreams H1–H8.
- `docs/deploy/ESTADO_DESPLEGUE.md` — estado global y decisiones.
- `docs/archive/deploy-handoffs/H6-deploy.md`, `H6-hil.md`, `H8.md`, `H9.md` — detalle técnico.
- `docs/SECURITY.md` — modelo de amenazas y safe-state.
- `backend/config/devices.yaml` — fuente de verdad de pines (LED virtual).
