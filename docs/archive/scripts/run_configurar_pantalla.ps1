<#
.SYNOPSIS
    Configura la pantalla XPT2046 en la Raspberry Pi — APLICA CAMBIOS Y REINICIA
.DESCRIPTION
    Instala dependencias, añade overlays a /boot/config.txt, habilita SPI,
    y reinicia la Raspberry Pi para aplicar los cambios.
    ¡LA PI SE REINICIARÁ! Espera ~60s antes de volver a conectarte.
.NOTES
    Usa paramiko (Python) para conexión SSH directa. NO depende del backend FastAPI.
#>

$ErrorActionPreference = "Continue"
$ProjectRoot = Split-Path -Parent $PSScriptRoot

Write-Host "╔══════════════════════════════════════════════════════════╗" -ForegroundColor Magenta
Write-Host "║   CONFIGURAR PANTALLA XPT2046 — Raspberry Pi           ║" -ForegroundColor Magenta
Write-Host "║   ⚠ La Pi se reiniciará al finalizar                   ║" -ForegroundColor Magenta
Write-Host "╚══════════════════════════════════════════════════════════╝" -ForegroundColor Magenta
Write-Host ""

# ── Confirmación ───────────────────────────────────────────────
Write-Host "⚠ ADVERTENCIA: Este script modificará /boot/config.txt y" -ForegroundColor Red
Write-Host "  REINICIARÁ la Raspberry Pi (192.168.88.211)." -ForegroundColor Red
Write-Host ""
$confirm = Read-Host "¿Continuar? (escribe 'SI' en mayúsculas)"

if ($confirm -ne "SI") {
    Write-Host "Cancelado por el usuario." -ForegroundColor Yellow
    exit 0
}

# ── Paso 1: Instalar dependencias ──────────────────────────────
Write-Host ""
Write-Host "[1/3] Instalando dependencias Python..." -ForegroundColor Yellow
pip install paramiko python-dotenv 2>&1 | Out-Null
Write-Host "      [OK] Dependencias listas" -ForegroundColor Green

# ── Paso 2: Ejecutar configuración ─────────────────────────────
Write-Host ""
Write-Host "[2/3] Aplicando configuración de pantalla..." -ForegroundColor Yellow
Write-Host ""

Set-Location $ProjectRoot
python scripts/pi_direct.py --setup-display --apply

# ── Paso 3: Verificar tras reinicio ────────────────────────────
Write-Host ""
Write-Host "[3/3] Esperando 70 segundos para que la Pi reinicie..." -ForegroundColor Yellow
Start-Sleep -Seconds 70

Write-Host ""
Write-Host "      Verificando /dev/fb0 tras reinicio..." -ForegroundColor Yellow
Write-Host ""

python scripts/pi_direct.py "ls -l /dev/fb* 2>&1"

Write-Host ""
Write-Host "══════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  Configuración completada." -ForegroundColor Cyan
Write-Host "  Si /dev/fb0 NO aparece, ejecuta de nuevo el diagnóstico:" -ForegroundColor White
Write-Host "  .\scripts\run_diagnostico.ps1" -ForegroundColor Green
Write-Host "══════════════════════════════════════════════════════════" -ForegroundColor Cyan
