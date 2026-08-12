# Instalación de Raspberry Pi OS en Raspberry Pi Model B+ V1.2

## Resumen

Esta guía cubre la instalación limpia de **Raspberry Pi OS Bullseye Lite 32-bit** en una tarjeta microSD para **Raspberry Pi Model B+ V1.2** (ARMv6, 512MB RAM).

Hardware confirmado:
- **Modelo:** Raspberry Pi Model B+ V1.2
- **CPU:** BCM2835 (ARM1176, ARMv6, single-core, 700 MHz)
- **RAM:** 512 MB
- **GPIO:** 40 pines (como Pi B+)
- **Pantalla:** 3.5" RPi Display 480x320 con controlador táctil XPT2046
- **Conexión red:** Ethernet integrado (no WiFi en B+)

---

## Requisitos previos

1. **MicroSD compatible:** 8GB mínimo (recomendado 16GB Class 10)
2. **Lector de microSD:** en tu PC de desarrollo
3. **Cable USB para alimentación:** 5V 2A mínimo
4. **Acceso a red Ethernet:** directamente desde tu router
5. **Software:**
   - **Raspberry Pi Imager** (descarga en tu PC)
   - **SSH client** (PowerShell en Windows, ssh en Linux/macOS)

---

## FASE 1: Preparación en el PC

### 1.1 Descargar Raspberry Pi Imager

Ve a: **https://www.raspberrypi.com/software/**

Descarga la versión para tu SO (Windows, macOS, Linux) e instálala.

### 1.2 Insertar microSD en el lector

Conecta el lector de microSD al PC con la tarjeta dentro.

---

## FASE 2: Crear imagen con Raspberry Pi Imager

### 2.1 Abre Raspberry Pi Imager

```
Raspberry Pi Imager → Abre la aplicación
```

### 2.2 Selecciona SO

**Botón: "CHOOSE OS"**

Navega a:
```
Raspberry Pi OS (Legacy) 
  → Raspberry Pi OS Lite (Legacy)
	  → 32-bit
```

**Por qué Legacy Lite 32-bit:**
- Bullseye Lite es la última versión que soporta ARMv6 (B+ V1.2)
- Legacy garantiza compatibilidad
- Lite ahorra recursos (sin GUI, solo CLI)
- 32-bit es obligatorio para ARMv6

### 2.3 Selecciona almacenamiento

**Botón: "CHOOSE STORAGE"**

Selecciona tu **microSD**. **CUIDADO:** asegúrate de que es la tarjeta correcta; esta operación borrará todos los datos.

### 2.4 Opciones avanzadas

**Botón: "NEXT"**

Se abrirá un diálogo con la opción "Edit settings". **Click en "EDIT SETTINGS":**

#### General
- **Hostname:** `raspberrypi` (o el nombre que prefieras)
- **Username:** `pi`
- **Password:** una contraseña segura (ej: `mi_contraseña_segura`)

#### Configuración de red
- **WiFi:** No aplica (B+ V1.2 no tiene WiFi)
- Usa Ethernet: conecta el cable Ethernet a tu router
- **SSID:** (déjalo en blanco)

#### Localización
- **Timezone:** Europe/Madrid (o tu zona horaria)
- **Keyboard layout:** es (Spanish) o en (English) según prefieras

#### Servicios
- **Enable SSH:** ✅ **SÍ, marcar obligatoriamente**
- **Use password authentication:** ✅ Sí (para primera conexión)

#### Guardado
- **Click: "SAVE"**

### 2.5 Comienza la escritura

Se pedirá confirmación:
```
¿Estás seguro de que quieres continuar? (Esto borrará todo en la microSD)
```

**Click: "YES, CONTINUE"**

**Espera 5-10 minutos** mientras se escribe y verifica la imagen.

Verás un mensaje:
```
Successfully written to /dev/...
```

**Eyecta la microSD** de forma segura.

---

## FASE 3: Arrancar la Raspberry Pi

### 3.1 Inserta la microSD

Inserta la microSD en la **ranura microSD de la Raspberry Pi B+** (debajo de la placa).

### 3.2 Conecta alimentación

Conecta un cable USB 5V 2A a la entrada **Micro-USB** de la Pi. **La Pi arrancará automáticamente.**

### 3.3 Conecta red

Conecta un cable **Ethernet** desde la Pi al router (la Pi B+ solo tiene Ethernet, no WiFi).

### 3.4 Espera al arranque

**Espera 1-2 minutos.** Los LED de la Pi parpadearán. Cuando se estabilicen (sin parpadeos rápidos), el SO está listo.

---

## FASE 4: Conexión SSH desde el PC

### 4.1 Encuentra la IP de la Pi

**En Linux/macOS:**
```sh
nmap -sn 192.168.1.0/24 | grep -i "raspberry\|bcm"
```

**En Windows PowerShell:**
Opción 1: Descarga **Advanced IP Scanner** (https://www.advanced-ip-scanner.com/) y busca dispositivos activos.

Opción 2: Conecta a tu router desde navegador y mira los dispositivos conectados.

**Típicamente la IP será algo como:** `192.168.1.X` (pregunta a tu router).

### 4.2 Conecta por SSH

**Windows (PowerShell):**
```powershell
ssh pi@192.168.1.X
# Reemplaza 192.168.1.X con la IP real
# Contraseña: la que configuraste en Imager (ej: tu_contraseña)
```

**Linux/macOS:**
```sh
ssh pi@192.168.1.X
```

Aceptarás la fingerprint SSH (escribe `yes`).

**Deberías ver el prompt:**
```
pi@raspberrypi:~ $
```

✅ **SSH funciona.**

---

## FASE 5: Actualizar el sistema

Desde la terminal SSH en la Pi:

```sh
sudo apt update
sudo apt upgrade -y
```

Espera a que termine (puede tardar 10-15 minutos en Pi B+ por ser lenta).

```sh
sudo apt install -y git curl wget build-essential python3-pip python3-venv python3-dev
```

Verifica Python:
```sh
python3 --version
# Debería mostrar: Python 3.9.x o similar
```

---

## FASE 6: Configuración de la pantalla XPT2046

### 6.1 Editar /boot/config.txt

En la Pi (SSH):

```sh
sudo nano /boot/config.txt
```

**Busca la sección `[pi]`** (suele estar al final).

**ANTES de `[pi]`, añade:**

```
# ===== Display Driver Configuration =====
# Pantalla: 3.5" RPi Display ILI9486 (480x320) + táctil XPT2046
# Bus: SPI0

# Habilitar SPI
dtparam=spi=on

# Habilitar I2C (por si lo necesitamos después)
dtparam=i2c_arm=on

# Driver de pantalla ILI9486 (framebuffer /dev/fb0)
# rotate=90 → rotación para orientación correcta
# speed=32000000 → velocidad SPI 32MHz
dtoverlay=ili9486,rotate=90,speed=32000000

# Driver táctil XPT2046 (ads7846)
# cs=1, penirq=25, rotate=270, swapxy=0
dtoverlay=ads7846,cs=1,penirq=25,speed=1000000,rotate=270,swapxy=0
```

**Guarda:** `Ctrl+O` → `Enter` → `Ctrl+X`

### 6.2 Reinicia la Pi

```sh
sudo reboot
```

Espera **1-2 minutos** a que reinicie. Desconecta/reconecta SSH.

### 6.3 Verifica framebuffer

```sh
ls -l /dev/fb*
```

Debería mostrar:
```
/dev/fb0   (el framebuffer de la pantalla)
```

Si aparece `/dev/fb0` → **la pantalla está detectada.**

Si ves:
```
ls: cannot access '/dev/fb*': No such file or directory
```

→ Los parámetros del overlay son incorrectos. Revisar `/boot/config.txt`.

### 6.4 Verifica entrada táctil

```sh
ls -l /dev/input/
```

Debería haber un dispositivo:
```
event0, event1, etc.
```

Confirma con:
```sh
cat /proc/bus/input/devices | grep -i "xpt\|ads"
```

---

## FASE 7: Instalar dependencias del proyecto

```sh
# En la Pi
cd /home/pi

# Clonar el repositorio (si aún no está)
git clone https://github.com/tu-usuario/Rpi_Pantalla_V1.git
cd Rpi_Pantalla_V1

# Crear entorno virtual Python
python3 -m venv .venv

# Activar entorno virtual
source .venv/bin/activate

# Actualizar pip
python -m pip install -U pip

# Instalar dependencias
pip install -r backend/requirements.txt
pip install pytest  # para tests
```

**Crea `backend/requirements.txt` si no existe:**

```
fastapi==0.104.0
uvicorn==0.24.0
pydantic==2.5.0
pyyaml==6.0.1
gpiozero==2.0.1
```

Verifica instalación:
```sh
python3 -c "from gpiozero import LED; print('✓ gpiozero OK')"
python3 -c "from fastapi import FastAPI; print('✓ FastAPI OK')"
python3 -c "from pydantic import BaseModel; print('✓ Pydantic OK')"
```

---

## FASE 8: Prueba GPIO

### 8.1 Cableado del LED

Conecta un LED al **Pin GPIO 17** (físicamente es el **pin 11 del cabezal GPIO**):
- **Positivo del LED** → **Pin 11 (GPIO 17)** con una resistencia 220Ω
- **Negativo del LED** → **Pin 6 (GND)**

[Referencia de pines: https://pinout.xyz/]

### 8.2 Prueba blink_test.py

```sh
# En la Pi, con venv activado
cd /home/pi/Rpi_Pantalla_V1
source .venv/bin/activate

# Ejecuta el test
python3 diagnostics/gpio/blink_test.py led1 --times 5
```

Deberías ver:
```
INFO: Setting up pin 17 as output
INFO: Blink 1/5: ON
INFO: Blink 1/5: OFF
...
INFO: Blink test finished for led1
```

**Y el LED parpadea 5 veces** → ✅ GPIO funciona.

---

## FASE 9: Ejecutar diagnóstico del sistema

```sh
# Genera un reporte completo
python3 diagnostics/run_diagnostics.py --output diagnostics/report

# Verifica los archivos generados
ls -la diagnostics/
# Debería haber: report.json y report.html
```

Descarga el archivo `report.html` por SCP para visualizar en tu PC:

**Desde tu PC:**
```powershell
# Windows PowerShell
scp pi@192.168.1.X:/home/pi/Rpi_Pantalla_V1/diagnostics/report.html ./report_pi.html
```

Abre `report_pi.html` en tu navegador. Verás:
- Modelo de CPU
- Módulos cargados (fbtft, ads7846, etc.)
- Devices de entrada (/dev/input/)
- Configuración de red
- Estado de SSH

---

## FASE 10: Configurar FastAPI para arranque automático (systemd)

**Crea el servicio systemd:**

```sh
sudo nano /etc/systemd/system/hmi-backend.service
```

**Contenido:**

```ini
[Unit]
Description=Raspberry HMI Backend Service
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/Rpi_Pantalla_V1
ExecStart=/home/pi/Rpi_Pantalla_V1/.venv/bin/uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**Guarda:** `Ctrl+O` → `Enter` → `Ctrl+X`

**Habilita el servicio:**

```sh
sudo systemctl daemon-reload
sudo systemctl enable hmi-backend.service
sudo systemctl start hmi-backend.service

# Verifica estado
sudo systemctl status hmi-backend.service
```

**Verifica que funciona:**

```sh
curl http://localhost:8000/health
# Debería devolver: {"status":"ok"}
```

---

## Troubleshooting

### Pantalla sigue en blanco

1. Verifica `/dev/fb0`:
   ```sh
   ls -l /dev/fb0
   ```
   Si no existe, el overlay no cargó.

2. Revisa dmesg:
   ```sh
   dmesg | grep -i ads7846
   dmesg | grep -i xpt
   ```

3. Parámetros comunes del overlay (prueba estos):
   - `rotate=0, 90, 180, 270`
   - `swapxy=0 o 1`
   - `penirq=24 o 25` (depende del cableado)

### SSH no funciona

1. Verifica que SSH está habilitado:
   ```sh
   sudo systemctl status ssh
   ```

2. Si está apagado:
   ```sh
   sudo systemctl start ssh
   sudo systemctl enable ssh
   ```

### GPIO no responde

1. Verifica permisos:
   ```sh
   id
   # ¿Eres grupo gpio? 
   groups pi
   ```

2. Si no, añade usuario a grupo gpio:
   ```sh
   sudo usermod -a -G gpio pi
   # Requiere logout/login o reboot
   ```

### gpiozero no encuentra GPIO

Verifica que no hay otro proceso usando los pines:
```sh
sudo lsof /dev/gpiomem
```

---

## Siguientes pasos

Una vez completada esta instalación:

1. ✅ Pantalla táctil debería estar funcional
2. ✅ GPIO debería responder
3. ✅ SSH debería estar operativo
4. ✅ FastAPI puede levantarse
5. ⏳ Implementar Frontend (React/Svelte + TypeScript)
6. ⏳ Integrar API + Frontend
7. ⏳ Configurar Kiosk (Chromium en pantalla táctil)

---

## Documentación de referencia

- **Pinout GPIO Pi B+:** https://pinout.xyz/
- **Overlay disponibles:** https://github.com/raspberrypi/linux/tree/rpi-6.1.y/arch/arm/boot/dts/overlays
- **gpiozero:** https://gpiozero.readthedocs.io/
- **FastAPI:** https://fastapi.tiangolo.com/
- **Raspberry Pi legacy:** https://www.raspberrypi.com/news/bullseye-legacy-is-here/

---

**Autor:** GitHub Copilot  
**Fecha:** 2026-01-15  
**Hardware:** Raspberry Pi Model B+ V1.2  
**Pantalla:** 3.5" RPi Display 480x320 XPT2046
