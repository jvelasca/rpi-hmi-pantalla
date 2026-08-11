#!/bin/bash
# setup_display.sh — Configura pantalla táctil XPT2046 en Raspberry Pi
set -e

echo "=== SETUP DISPLAY XPT2046 ==="

# 1. Diagnosticar estado actual
echo "[1] Estado actual:"
ls -l /dev/fb* 2>&1 || echo "  NO /dev/fb*"
grep ili9486 /boot/config.txt 2>/dev/null || echo "  NO overlay ili9486"
grep ads7846 /boot/config.txt 2>/dev/null || echo "  NO overlay ads7846"
ls -l /dev/input/ 2>&1

# 2. Si no hay framebuffer, configurar
if [ ! -e /dev/fb0 ]; then
    echo ""
    echo "[2] Configurando pantalla..."
    
    # Backup
    sudo cp /boot/config.txt /boot/config.txt.backup
    echo "  Backup creado: /boot/config.txt.backup"
    
    # Agregar spi=on si no existe
    if ! grep -q "dtparam=spi=on" /boot/config.txt 2>/dev/null; then
        echo "dtparam=spi=on" | sudo tee -a /boot/config.txt
        echo "  spi=on agregado"
    fi
    
    # Agregar overlay ili9486 (driver de pantalla) si no existe
    if ! grep -q "ili9486" /boot/config.txt 2>/dev/null; then
        echo "dtoverlay=ili9486,rotate=90,speed=32000000" | sudo tee -a /boot/config.txt
        echo "  overlay ili9486 agregado (driver display)"
    fi
    
    # Agregar overlay ads7846 (táctil) si no existe
    if ! grep -q "ads7846" /boot/config.txt 2>/dev/null; then
        echo "dtoverlay=ads7846,cs=1,penirq=25,speed=1000000,rotate=270,swapxy=0" | sudo tee -a /boot/config.txt
        echo "  overlay ads7846 agregado (táctil)"
    fi
    
    echo ""
    echo "[3] Verificando config.txt:"
    grep -E "dtoverlay|ads7846|ili9486|dtparam=spi" /boot/config.txt
    
    echo ""
    echo "[4] REINICIANDO en 3 segundos..."
    sleep 3
    sudo reboot
else
    echo ""
    echo "[2] /dev/fb0 ya existe. Verificando touch..."
    cat /proc/bus/input/devices 2>/dev/null | grep -iE "Name|xpt|ads|touch" || echo "  No touch detectado"
    
    echo ""
    echo "[3] Prueba de framebuffer:"
    sudo dd if=/dev/urandom of=/dev/fb0 bs=480 count=320 2>/dev/null
    sleep 1
    sudo dd if=/dev/zero of=/dev/fb0 bs=480 count=320 2>/dev/null
    echo "  Prueba completada (ruido -> negro)"
fi

echo ""
echo "=== SETUP COMPLETADO ==="
