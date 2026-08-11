<#
.SYNOPSIS
    Diagnóstico de pantalla en Raspberry Pi — instala dependencias y ejecuta pi_direct.py
.DESCRIPTION
    Instala paramiko + python-dotenv si es necesario y ejecuta el diagnóstico
    completo de la pantalla táctil XPT2046 en la Raspberry Pi.
.NOTES
    Usa paramiko (Python) para conexión SSH directa. NO depende del backend FastAPI.
#>

$ErrorActionPreference = "Continue"
$ProjectRoot = Split-Path -Parent $PSScriptRoot

Write-Host "╔══════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║   DIAGNÓSTICO DE PANTALLA — Raspberry Pi               ║" -ForegroundColor Cyan
Write-Host "╚══════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# ── Paso 1: Instalar dependencias ──────────────────────────────
Write-Host "[1/2] Instalando dependencias Python..." -ForegroundColor Yellow
pip install paramiko python-dotenv 2>&1 | Out-Null
if ($LASTEXITCODE -eq 0 -or $LASTEXITCODE -eq $null) {
    Write-Host "      [OK] Dependencias listas" -ForegroundColor Green
} else {
    Write-Host "      [WARN] Posible error con pip, continuando..." -ForegroundColor Yellow
}

# ── Paso 2: Ejecutar diagnóstico ───────────────────────────────
Write-Host ""
Write-Host "[2/2] Ejecutando diagnóstico en la Pi..." -ForegroundColor Yellow
Write-Host ""

Set-Location $ProjectRoot
python scripts/pi_direct.py --diagnose-display

Write-Host ""
Write-Host "══════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  Diagnóstico completado." -ForegroundColor Cyan
Write-Host ""
Write-Host "  Si la pantalla NO está configurada, ejecuta:" -ForegroundColor White
Write-Host "  .\scripts\run_configurar_pantalla.ps1" -ForegroundColor Green
Write-Host "══════════════════════════════════════════════════════════" -ForegroundColor Cyan
