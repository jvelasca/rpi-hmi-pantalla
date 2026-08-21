<#
.SYNOPSIS
    Conecta la app Rpi_Pantalla_V1 a la Raspberry Pi y ejecuta pruebas.

.DESCRIPTION
    1. Instala paramiko + python-dotenv
    2. Arranca el backend FastAPI
    3. Conecta SSH a la Pi
    4. Ejecuta comando remoto (uname -a)
    5. Muestra diagnóstico del sistema remoto
#>

$ErrorActionPreference = "Continue"
$ProjectRoot = "E:\SINCRONIZADO\Informatica\Proyectos VisualStudio\Python\Rapsberry\Rpi_Pantalla_V1"
$PiIP = if ($env:RPI_HOST) { $env:RPI_HOST } else { "192.168.88.211" }
$PiUser = if ($env:RPI_USER) { $env:RPI_USER } else { "pi" }
$PiPass = if ($env:RPI_PASSWORD) { $env:RPI_PASSWORD } else { "" }

if (-not $PiPass) {
    Write-Host "[ERROR] Define RPI_PASSWORD en variables de entorno" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "══════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "   Rpi_Pantalla_V1 — Conexión a Raspberry Pi" -ForegroundColor Cyan
Write-Host "   Target: $PiIP" -ForegroundColor Cyan
Write-Host "══════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""

# ── Paso 1: Instalar dependencias ────────────────────────
Write-Host "━━━ Paso 1/5: Instalando dependencias ━━━" -ForegroundColor Yellow
pip install paramiko python-dotenv 2>&1
if ($LASTEXITCODE -eq 0) { Write-Host "  [OK] Dependencias instaladas" -ForegroundColor Green }
else { Write-Host "  [WARN] Puede que ya estuvieran instaladas" -ForegroundColor Yellow }

# ── Paso 2: Verificar que la Pi responde ─────────────────
Write-Host ""
Write-Host "━━━ Paso 2/5: Verificando que la Pi responde ━━━" -ForegroundColor Yellow
$ping = Test-Connection -ComputerName $PiIP -Count 1 -Quiet -ErrorAction SilentlyContinue
if ($ping) {
    Write-Host "  [OK] $PiIP responde a ping" -ForegroundColor Green
} else {
    Write-Host "  [WARN] $PiIP no responde a ping. ¿Está encendida?" -ForegroundColor Yellow
}

# Verificar puerto SSH
try {
    $tcp = New-Object System.Net.Sockets.TcpClient
    $task = $tcp.ConnectAsync($PiIP, 22)
    if ($task.Wait(2000) -and $tcp.Connected) {
        Write-Host "  [OK] Puerto SSH (22) abierto en $PiIP" -ForegroundColor Green
        $tcp.Close()
    } else {
        Write-Host "  [WARN] Puerto SSH (22) NO responde en $PiIP" -ForegroundColor Yellow
        $tcp.Close()
    }
} catch {
    Write-Host "  [WARN] No se pudo verificar SSH: $_" -ForegroundColor Yellow
}

# ── Paso 3: Arrancar backend ─────────────────────────────
Write-Host ""
Write-Host "━━━ Paso 3/5: Arrancando backend FastAPI ━━━" -ForegroundColor Yellow
Write-Host "  Iniciando servidor en http://localhost:8000 ..."

# Matar instancia previa
Get-Process -Name "python" -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -match "uvicorn" } | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 1

# Arrancar en background
$backendJob = Start-Job -ScriptBlock {
    param($root)
    Set-Location $root
    python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 2>&1
} -ArgumentList $ProjectRoot

Write-Host "  Esperando que el backend arranque..."
Start-Sleep -Seconds 3

# Verificar que responde
try {
    $health = Invoke-RestMethod -Uri "http://localhost:8000/health" -TimeoutSec 5 -ErrorAction Stop
    if ($health.status -eq "ok") {
        Write-Host "  [OK] Backend respondiendo en http://localhost:8000/health" -ForegroundColor Green
    }
} catch {
    Write-Host "  [WARN] Backend no responde aún. Revisa los logs del job." -ForegroundColor Yellow
}

# ── Paso 4: Conectar SSH y ejecutar comando ──────────────
Write-Host ""
Write-Host "━━━ Paso 4/5: Probando conexión SSH a la Pi ━━━" -ForegroundColor Yellow

$body = @{
    host = $PiIP
    user = $PiUser
    password = $PiPass
    port = 22
    timeout = 15
} | ConvertTo-Json

Write-Host "  Conectando a $PiIP ..."
try {
    $connectResult = Invoke-RestMethod -Uri "http://localhost:8000/api/ssh/connect" -Method Post -Body $body -ContentType "application/json" -TimeoutSec 20 -ErrorAction Stop
    Write-Host "  [OK] $($connectResult.message)" -ForegroundColor Green

    # Ejecutar uname -a
    Write-Host ""
    Write-Host "  Ejecutando 'uname -a' en la Pi..."
    $execBody = @{ command = "uname -a" } | ConvertTo-Json
    $execResult = Invoke-RestMethod -Uri "http://localhost:8000/api/ssh/execute" -Method Post -Body $execBody -ContentType "application/json" -TimeoutSec 20
    Write-Host "  [OK] Sistema remoto:" -ForegroundColor Green
    Write-Host "       $($execResult.stdout)" -ForegroundColor White

    # Hostname
    Write-Host ""
    Write-Host "  Ejecutando 'hostname' en la Pi..."
    $hostBody = @{ command = "hostname" } | ConvertTo-Json
    $hostResult = Invoke-RestMethod -Uri "http://localhost:8000/api/ssh/execute" -Method Post -Body $hostBody -ContentType "application/json" -TimeoutSec 20
    Write-Host "       Hostname: $($hostResult.stdout)" -ForegroundColor White
} catch {
    Write-Host "  [ERROR] Fallo conectando SSH: $_" -ForegroundColor Red
    if ($_.Exception.Response) {
        $reader = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())
        $errBody = $reader.ReadToEnd()
        Write-Host "  Detalle: $errBody" -ForegroundColor Red
    }
}

# ── Paso 5: Diagnóstico ──────────────────────────────────
Write-Host ""
Write-Host "━━━ Paso 5/5: Diagnóstico remoto ━━━" -ForegroundColor Yellow
try {
    $diagResult = Invoke-RestMethod -Uri "http://localhost:8000/api/deploy/diagnostics" -TimeoutSec 30 -ErrorAction Stop
    Write-Host "  [OK] Diagnóstico: $($diagResult.message)" -ForegroundColor Green
} catch {
    Write-Host "  [WARN] Diagnóstico no disponible: $_" -ForegroundColor Yellow
}

# ── Resumen ──────────────────────────────────────────────
Write-Host ""
Write-Host "══════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "   Backend:  http://localhost:8000" -ForegroundColor Green
Write-Host "   API Docs: http://localhost:8000/docs" -ForegroundColor Green
Write-Host "   SSH:      $PiIP (pi@$PiIP)" -ForegroundColor Green
Write-Host "══════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""
Write-Host "Para detener el backend: Stop-Job -Id $($backendJob.Id)" -ForegroundColor Yellow
Write-Host "O cierra esta ventana de PowerShell." -ForegroundColor Yellow
