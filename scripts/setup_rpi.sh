#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════
# setup_rpi.sh — Configuración automatizada de la Raspberry Pi
# ═══════════════════════════════════════════════════════════════════════
#
# Este script se ejecuta DENTRO de la Raspberry Pi (copiado vía SSH).
# Realiza todas las configuraciones necesarias para el proyecto HMI.
#
# Uso (desde la Pi):
#   chmod +x setup_rpi.sh
#   ./setup_rpi.sh
#
# O remotamente desde PowerShell:
#   scp scripts\setup_rpi.sh pi@<IP>:/home/pi/
#   ssh pi@<IP> "chmod +x setup_rpi.sh && ./setup_rpi.sh"
# ═══════════════════════════════════════════════════════════════════════

set -euo pipefail  # Fallar rápido ante cualquier error

# ── Colores ───────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; NC='\033[0m'
ok()   { echo -e "${GREEN}[OK]${NC} $*"; }
info() { echo -e "${CYAN}[INFO]${NC} $*"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
err()  { echo -e "${RED}[ERROR]${NC} $*"; }

echo ""
echo -e "${CYAN}══════════════════════════════════════════════════════${NC}"
echo -e "${CYAN}   Raspberry Pi Setup - Rpi_Pantalla_V1${NC}"
echo -e "${CYAN}══════════════════════════════════════════════════════${NC}"
echo ""

# ── 1. Verificar SO ───────────────────────────────────────────────────
echo -e "${YELLOW}━━━ FASE 1: Información del sistema ━━━${NC}"
info "Modelo: $(cat /proc/device-tree/model 2>/dev/null || echo 'desconocido')"
info "Kernel: $(uname -r)"
info "Arquitectura: $(uname -m)"
source /etc/os-release 2>/dev/null || true
info "SO: ${PRETTY_NAME:-desconocido}"
info "Hostname: $(hostname)"
info "IP local: $(hostname -I 2>/dev/null || echo 'no detectada')"

# ── 2. Verificar hardware ─────────────────────────────────────────────
echo ""
echo -e "${YELLOW}━━━ FASE 2: Verificación de hardware ━━━${NC}"

# GPIO
if [ -e /dev/gpiomem ]; then
    ok "/dev/gpiomem encontrado — GPIO accesible"
elif [ -e /dev/mem ]; then
    warn "/dev/gpiomem no encontrado, pero /dev/mem existe"
else
    err "No se encontró acceso a GPIO. ¿Está habilitado en /boot/config.txt?"
fi

# Framebuffer (pantalla)
if ls /dev/fb* 1>/dev/null 2>&1; then
    ok "Framebuffer(s) detectado(s): $(ls /dev/fb* 2>/dev/null | tr '\n' ' ')"
else
    warn "No se detectó framebuffer. La pantalla puede no estar configurada."
fi

# SPI (para pantalla táctil)
if [ -e /dev/spidev0.0 ] || [ -e /dev/spidev0.1 ]; then
    ok "SPI detectado — necesario para pantalla XPT2046"
else
    warn "SPI no detectado. Verifica /boot/config.txt (dtparam=spi=on)"
fi

# I2C
if [ -e /dev/i2c-1 ]; then
    ok "I2C detectado"
else
    warn "I2C no detectado"
fi

# ── 3. Verificar Python y venv ────────────────────────────────────────
echo ""
echo -e "${YELLOW}━━━ FASE 3: Entorno Python ━━━${NC}"

if command -v python3 &>/dev/null; then
    PY_VERSION=$(python3 --version)
    ok "Python encontrado: $PY_VERSION"
else
    err "Python 3 no encontrado. Instala con: sudo apt install python3 python3-pip python3-venv"
    exit 1
fi

# Verificar versión mínima (3.8+)
PY_MAJOR=$(python3 -c "import sys; print(sys.version_info.major)")
PY_MINOR=$(python3 -c "import sys; print(sys.version_info.minor)")
if [ "$PY_MAJOR" -lt 3 ] || { [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 8 ]; }; then
    err "Se requiere Python 3.8+. Versión actual: $PY_VERSION"
    exit 1
fi

# ── 4. Instalar paquetes del sistema necesarios ───────────────────────
echo ""
echo -e "${YELLOW}━━━ FASE 4: Paquetes del sistema ━━━${NC}"
REQUIRED_PKGS="git curl wget python3-pip python3-venv python3-dev"
MISSING_PKGS=""

for pkg in $REQUIRED_PKGS; do
    if ! dpkg -l "$pkg" 2>/dev/null | grep -q "^ii"; then
        MISSING_PKGS="$MISSING_PKGS $pkg"
    fi
done

if [ -n "$MISSING_PKGS" ]; then
    warn "Faltan paquetes:$MISSING_PKGS"
    info "Instalando..."
    sudo apt update -qq
    sudo apt install -y $MISSING_PKGS
    ok "Paquetes instalados"
else
    ok "Todos los paquetes del sistema están presentes"
fi

# ── 5. Configurar entorno virtual Python ──────────────────────────────
echo ""
echo -e "${YELLOW}━━━ FASE 5: Entorno virtual Python ━━━${NC}"

PROJECT_DIR="/home/pi/rpi_hmi"
cd "$PROJECT_DIR" 2>/dev/null || {
    warn "Directorio del proyecto no encontrado en $PROJECT_DIR"
    info "¿Clonar repositorio? (s/n)"
    read -r RESP
    if [ "$RESP" = "s" ] || [ "$RESP" = "S" ]; then
        info "URL del repositorio Git:"
        read -r REPO_URL
        git clone "$REPO_URL" "$PROJECT_DIR"
        ok "Repositorio clonado"
        cd "$PROJECT_DIR"
    else
        err "No se puede continuar sin el proyecto."
        exit 1
    fi
}

VENV_DIR="$PROJECT_DIR/venv"
if [ -d "$VENV_DIR" ]; then
    info "Entorno virtual ya existe en venv"
else
    info "Creando entorno virtual en venv..."
    python3 -m venv "$VENV_DIR"
    ok "Entorno virtual creado"
fi

# Activar venv
source "$VENV_DIR/bin/activate"
info "Entorno virtual activado"

# Actualizar pip
info "Actualizando pip..."
python -m pip install --upgrade pip -q

# ── 6. Instalar dependencias Python ───────────────────────────────────
echo ""
echo -e "${YELLOW}━━━ FASE 6: Dependencias Python ━━━${NC}"

REQ_FILE="$PROJECT_DIR/backend/requirements.txt"
if [ -f "$REQ_FILE" ]; then
    info "Instalando dependencias desde requirements.txt..."
    # RPi.GPIO puede fallar en Bullseye/Bookworm — lo intentamos pero no es bloqueante
    pip install -r "$REQ_FILE" 2>&1 | tee /tmp/pip_install.log || {
        warn "Algunas dependencias fallaron. Revisando..."
        # Reintentar sin RPi.GPIO (obsoleto en sistemas modernos)
        grep -v "RPi.GPIO" "$REQ_FILE" > /tmp/requirements_safe.txt
        pip install -r /tmp/requirements_safe.txt
        ok "Dependencias instaladas (sin RPi.GPIO — se usará gpiozero/lgpio)"
    }
    ok "Dependencias instaladas"
else
    err "No se encontró $REQ_FILE"
    exit 1
fi

# ── 7. Verificar la instalación ──────────────────────────────────────
echo ""
echo -e "${YELLOW}━━━ FASE 7: Verificación ━━━${NC}"

# Verificar FastAPI
python -c "import fastapi; print('FastAPI', fastapi.__version__)" && ok "FastAPI funciona" || err "FastAPI falló"

# Verificar gpiozero
python -c "import gpiozero; print('gpiozero OK')" && ok "gpiozero funciona" || warn "gpiozero falló (normal en PC sin GPIO)"

# Verificar PyYAML
python -c "import yaml; print('PyYAML', yaml.__version__)" && ok "PyYAML funciona" || err "PyYAML falló"

# ── 8. Ejecutar diagnósticos ──────────────────────────────────────────
echo ""
echo -e "${YELLOW}━━━ FASE 8: Diagnósticos del sistema ━━━${NC}"
if [ -f "$PROJECT_DIR/diagnostics/run_diagnostics.py" ]; then
    info "Ejecutando diagnóstico del sistema..."
    python "$PROJECT_DIR/diagnostics/run_diagnostics.py" --output "$PROJECT_DIR/diagnostics/report"
    ok "Reporte generado en diagnostics/report.json y diagnostics/report.html"
else
    warn "Script de diagnóstico no encontrado"
fi

# ── 9. Probar GPIO (mock) ─────────────────────────────────────────────
echo ""
echo -e "${YELLOW}━━━ FASE 9: Test GPIO ━━━${NC}"
if [ -f "$PROJECT_DIR/diagnostics/gpio/blink_test.py" ]; then
    info "Ejecutando blink_test (modo mock)..."
    python "$PROJECT_DIR/diagnostics/gpio/blink_test.py" led1 --times 2 && ok "Blink test OK" || warn "Blink test falló"
else
    warn "blink_test.py no encontrado"
fi

# ── 10. Iniciar backend ───────────────────────────────────────────────
echo ""
echo -e "${YELLOW}━━━ FASE 10: Backend FastAPI ━━━${NC}"
info "Iniciando servidor FastAPI en segundo plano (puerto 8000)..."
cd "$PROJECT_DIR"
sudo systemctl start rpi-hmi-backend.service 2>/dev/null && \
    echo "SYSTEMCTL_OK" || echo "SYSTEMCTL_FAIL"
sleep 2

if systemctl is-active --quiet rpi-hmi-backend.service; then
    ok "Backend iniciado via systemctl"
    ok "Accede desde tu PC a: http://$(hostname -I | awk '{print $1}'):8000/health"
    info "Logs: sudo journalctl -u rpi-hmi-backend.service -f"
else
    err "El backend no se inició. Revisa: sudo journalctl -u rpi-hmi-backend.service"
    err "Asegurate de haber ejecutado --install-service primero."
fi

# ── Resumen ────────────────────────────────────────────────────────────
echo ""
echo -e "${CYAN}══════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}   Configuración completada${NC}"
echo -e "${CYAN}══════════════════════════════════════════════════════${NC}"
echo ""
echo "  Backend:  http://$(hostname -I | awk '{print $1}'):8000/health"
echo "  API Docs: http://$(hostname -I | awk '{print $1}'):8000/docs"
echo "  Logs:     tail -f /tmp/hmi_backend.log"
echo "  Detener:  kill \$(cat /tmp/hmi_backend.pid)"
echo ""
