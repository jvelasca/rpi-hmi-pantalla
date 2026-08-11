#!/bin/bash
# start_hmi.sh — Libera la TFT y lanza la app HMI Pygame DRM
#
# Uso:
#   ssh pi@192.168.88.211
#   cd /home/pi/rpi_hmi
#   ./scripts/start_hmi.sh
#
# O remoto:
#   ssh pi@192.168.88.211 'cd /home/pi/rpi_hmi && sudo ./scripts/start_hmi.sh'
#
# Lo que hace:
#   1. Detiene lightdm (Wayland compositor labwc) -> libera /dev/dri/card0
#   2. Desvincula la consola virtual del fb1 (ili9486)
#   3. Lanza display/app.py con driver DRM/KMS en card0
#   4. Al salir (Ctrl+C), restaura lightdm opcionalmente

set -e

HMI_DIR="/home/pi/rpi_hmi"
VENV_PYTHON="$HMI_DIR/venv/bin/python3"
RESTORE_LIGHTDM=true   # cambiar a false si no quieres restaurar el escritorio

echo "============================================"
echo " RPi HMI — Arranque display fisico (DRM/KMS)"
echo "============================================"

# ── Paso 1: Detener lightdm (libera /dev/dri/card0) ──
echo ""
echo "[1/4] Deteniendo lightdm para liberar /dev/dri/card0..."

if systemctl is-active --quiet lightdm 2>/dev/null; then
    sudo systemctl stop lightdm
    sleep 2
    echo "       lightdm detenido."
else
    echo "       lightdm ya estaba detenido."
fi

# Verificar que card0 esta libre
if sudo fuser /dev/dri/card0 2>/dev/null; then
    echo "       [WARN] /dev/dri/card0 sigue en uso. Intentando forzar..."
    sudo fuser -k /dev/dri/card0 2>/dev/null || true
    sleep 1
fi

# ── Paso 2: Desvincular consola virtual del fb1 ──
echo ""
echo "[2/4] Desvinculando consola virtual de /dev/fb1 (ili9486)..."

if [ -w /sys/class/vtconsole/vtcon1/bind ]; then
    echo 0 | sudo tee /sys/class/vtconsole/vtcon1/bind > /dev/null 2>&1 || true
    echo "       vtcon1 desvinculada de fb1."
else
    echo "       vtcon1 no disponible o ya desvinculada."
fi

# ── Paso 3: Configurar entorno y permisos ──
echo ""
echo "[3/4] Configurando entorno..."

export SDL_VIDEODRIVER=kmsdrm
export SDL_KMSDRM_DEVICE_INDEX=0
export SDL_RENDER_DRIVER=software
export PYTHONPATH="$HMI_DIR"
export PYTHONUNBUFFERED=1

# Asegurar que el usuario pi pertenece al grupo video
if ! groups pi | grep -q video; then
    echo "       Añadiendo pi al grupo video..."
    sudo usermod -a -G video pi
    echo "       [WARN] Grupo video añadido. Cierra sesion SSH y vuelve a entrar."
    echo "       Luego ejecuta este script de nuevo."
    exit 0
fi

# ── Paso 4: Lanzar la app HMI ──
echo ""
echo "[4/4] Lanzando display/app.py..."
echo ""
echo "   Controles:"
echo "     - ESC   -> Salir"
echo "     - Ctrl+C -> Salir (si se ejecuta desde terminal)"
echo "     - Tocar la pantalla -> Interactuar con widgets"
echo ""

cd "$HMI_DIR"

# Ejecutar como root si es necesario para DRM
if [ "$(whoami)" = "root" ]; then
    exec "$VENV_PYTHON" -m display.app --debug --api-url http://localhost:8000
elif [ -r /dev/dri/card0 ] && [ -w /dev/dri/card0 ]; then
    exec "$VENV_PYTHON" -m display.app --debug --api-url http://localhost:8000
else
    echo "       Ejecutando con sudo para acceso a /dev/dri/card0..."
    exec sudo -E "$VENV_PYTHON" -m display.app --debug --api-url http://localhost:8000
fi

# ── Cleanup (se ejecuta solo si el script no usa 'exec') ──
echo ""
echo "HMI cerrada."

if [ "$RESTORE_LIGHTDM" = true ]; then
    echo "Restaurando lightdm..."
    sudo systemctl start lightdm
fi
