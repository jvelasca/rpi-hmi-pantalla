<#
.SYNOPSIS
    Orquestador completo: encuentra la Raspberry Pi, configura todo y despliega la app.

.DESCRIPTION
    Este script ejecuta todo el flujo de trabajo:
    1. Encuentra la Raspberry Pi en la red local
    2. Copia los archivos del proyecto a la Pi vía SCP
    3. Ejecuta el script de configuración (setup_rpi.sh) en la Pi
    4. Verifica que el backend responde correctamente

.PARAMETER Ip
    IP de la Raspberry Pi. Si no se especifica, se busca automáticamente.

.PARAMETER User
    Usuario SSH (por defecto "pi").

.PARAMETER SkipFind
    Salta la fase de búsqueda y va directo a la IP especificada.

.PARAMETER SkipSetup
    Salta la configuración (útil si ya está configurada).

.PARAMETER OnlyDiagnostics
    Solo ejecuta diagnósticos, sin instalar ni configurar.

.EXAMPLE
    .\full_deploy.ps1
    .\full_deploy.ps1 -Ip 192.168.1.100
    .\full_deploy.ps1 -SkipFind -Ip 192.168.1.100 -SkipSetup
    .\full_deploy.ps1 -OnlyDiagnostics
#>
[CmdletBinding()]
param(
    [string]$Ip,
    [string]$User = "pi",
    [switch]$SkipFind,
    [switch]$SkipSetup,
    [switch]$OnlyDiagnostics
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir

# ── Funciones de logging ──────────────────────────────────────────────
function Write-OK   { Write-Host "  [OK] " -NoNewline -ForegroundColor Green; Write-Host $args[0] }
function Write-INFO { Write-Host " [INFO] " -NoNewline -ForegroundColor Cyan; Write-Host $args[0] }
function Write-WARN { Write-Host " [WARN] " -NoNewline -ForegroundColor Yellow; Write-Host $args[0] }
function Write-ERR  { Write-Host " [ERROR] " -NoNewline -ForegroundColor Red; Write-Host $args[0] }
function Write-STEP { Write-Host ""; Write-Host "━━━ $($args[0]) ━━━" -ForegroundColor Yellow }

# ── Banner ────────────────────────────────────────────────────────────
Clear-Host
Write-Host ""
Write-Host "╔══════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║   Rpi_Pantalla_V1 — Despliegue Automático Completo            ║" -ForegroundColor Cyan
Write-Host "║   Raspberry Pi Model B+ V1.2  |  HMI Platform                ║" -ForegroundColor Cyan
Write-Host "╚══════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# ── FASE 1: Encontrar la Raspberry Pi ─────────────────────────────────
if (-not $SkipFind -and -not $Ip) {
    Write-STEP "FASE 1/5: Buscando Raspberry Pi en la red"
    
    $finderScript = Join-Path $ScriptDir "find_and_connect.ps1"
    if (-not (Test-Path $finderScript)) {
        Write-ERR "No se encontró find_and_connect.ps1 en $ScriptDir"
        Write-INFO "Asegúrate de que el script existe y vuelve a intentarlo."
        exit 1
    }
    
    # Ejecutar finder en modo no interactivo (sin pregunta final)
    Write-INFO "Ejecutando find_and_connect.ps1..."
    try {
        # Usamos un approach más directo: escanear con arp -a y ping
        Write-INFO "Escaneando red local..."
        
        # Obtener tabla ARP
        $arpOutput = arp -a 2>$null
        Write-INFO "Tabla ARP obtenida. Analizando..."
        
        # Buscar IPs activas con puerto 22
        $arpLines = $arpOutput -split "`n" | Where-Object { $_ -match '(\d+\.\d+\.\d+\.\d+)' }
        $candidates = @()
        foreach ($line in $arpLines) {
            if ($line -match '(\d+\.\d+\.\d+\.\d+)') {
                $ip = $Matches[1]
                if ($ip -ne "255.255.255.255" -and $ip -notlike "224.*" -and $ip -notlike "239.*") {
                    $candidates += $ip
                }
            }
        }
        
        Write-INFO "Candidatos desde ARP: $($candidates.Count) dispositivos"
        
        # Probar SSH en cada candidato
        $found = $false
        foreach ($candidate in $candidates) {
            Write-INFO "Probando SSH en $candidate ..."
            try {
                $tcp = New-Object System.Net.Sockets.TcpClient
                $connectTask = $tcp.ConnectAsync($candidate, 22)
                if ($connectTask.Wait(1500) -and $tcp.Connected) {
                    $tcp.Close()
                    Write-OK "SSH disponible en $candidate"
                    
                    # Verificar que es una Raspberry Pi leyendo el banner SSH
                    $Ip = $candidate
                    $found = $true
                    break
                }
                $tcp.Close()
            }
            catch {
                # Continuar
            }
        }
        
        if (-not $found) {
            Write-WARN "No se encontró SSH en los candidatos ARP. Probando IPs comunes..."
            $commonSubnets = @("192.168.1", "192.168.0", "10.0.0")
            $foundCommon = $false
            foreach ($subnet in $commonSubnets) {
                for ($i = 1; $i -le 20; $i++) {
                    $testIp = "$subnet.$i"
                    try {
                        $tcp = New-Object System.Net.Sockets.TcpClient
                        $connectTask = $tcp.ConnectAsync($testIp, 22)
                        if ($connectTask.Wait(500) -and $tcp.Connected) {
                            $tcp.Close()
                            Write-OK "SSH disponible en $testIp"
                            $Ip = $testIp
                            $foundCommon = $true
                            break
                        }
                        $tcp.Close()
                    }
                    catch { }
                }
                if ($foundCommon) { break }
            }
            
            if (-not $foundCommon) {
                Write-ERR "No se pudo encontrar la Raspberry Pi automáticamente."
                Write-Host ""
                Write-INFO "Por favor, especifica la IP manualmente:"
                Write-Host "       .\full_deploy.ps1 -Ip <DIRECCIÓN_IP>" -ForegroundColor Yellow
                Write-Host ""
                $manualIp = Read-Host "O introduce la IP ahora (Enter para cancelar)"
                if ($manualIp) { $Ip = $manualIp } else { exit 1 }
            }
        }
    }
    catch {
        Write-ERR "Error durante el escaneo: $_"
        exit 1
    }
}

Write-OK "Raspberry Pi objetivo: $Ip"
Write-INFO "Usuario: $User"

# ── FASE 2: Verificar conexión SSH ────────────────────────────────────
Write-STEP "FASE 2/5: Verificando conexión SSH con $Ip"

Write-INFO "Probando SSH... (se te pedirá la contraseña)"
Write-HOST "   Contraseñas a probar: RaspberryB+2026! o raspberry" -ForegroundColor DarkGray
Write-Host ""

# Probar conexión con comando simple
$sshTest = ssh -o "StrictHostKeyChecking=accept-new" -o "ConnectTimeout=10" -o "BatchMode=no" "$User@$Ip" "echo 'SSH_OK' && hostname && uname -a" 2>&1
if ($LASTEXITCODE -eq 0 -and $sshTest -match "SSH_OK") {
    Write-OK "Conexión SSH exitosa"
    Write-INFO "Hostname remoto: $(($sshTest -split "`n")[1])"
    Write-INFO "Sistema remoto: $(($sshTest -split "`n")[2])"
}
else {
    Write-WARN "La prueba SSH no fue limpia. ¿Deseas intentar una conexión interactiva? (s/n)"
    $resp = Read-Host
    if ($resp -eq "s") {
        ssh "$User@$Ip"
    }
    else {
        Write-INFO "Continuando de todas formas..."
    }
}

# ── FASE 3: Copiar archivos del proyecto a la Pi ──────────────────────
if (-not $SkipSetup) {
    Write-STEP "FASE 3/5: Copiando archivos del proyecto a la Raspberry Pi"
    
    $remoteDir = "/home/pi/Rpi_Pantalla_V1"
    
    # Crear estructura de directorios remota
    Write-INFO "Creando estructura de directorios en la Pi..."
    ssh "$User@$Ip" "mkdir -p $remoteDir/backend/app/hardware $remoteDir/backend/config $remoteDir/diagnostics/gpio $remoteDir/scripts $remoteDir/infra"
    
    # Copiar archivos uno a uno (más fiable que copiar todo el directorio)
    $filesToCopy = @(
        @{Local = "$ProjectRoot\backend\app\main.py";            Remote = "$remoteDir/backend/app/main.py"},
        @{Local = "$ProjectRoot\backend\app\hardware\hal.py";     Remote = "$remoteDir/backend/app/hardware/hal.py"},
        @{Local = "$ProjectRoot\backend\config\devices.yaml";     Remote = "$remoteDir/backend/config/devices.yaml"},
        @{Local = "$ProjectRoot\backend\requirements.txt";        Remote = "$remoteDir/backend/requirements.txt"},
        @{Local = "$ProjectRoot\diagnostics\run_diagnostics.py";  Remote = "$remoteDir/diagnostics/run_diagnostics.py"},
        @{Local = "$ProjectRoot\diagnostics\gpio\blink_test.py";  Remote = "$remoteDir/diagnostics/gpio/blink_test.py"},
        @{Local = "$ScriptDir\setup_rpi.sh";                      Remote = "$remoteDir/scripts/setup_rpi.sh"}
    )
    
    foreach ($file in $filesToCopy) {
        if (Test-Path $file.Local) {
            Write-INFO "Copiando: $(Split-Path $file.Local -Leaf) → $($file.Remote)"
            scp -q -o "StrictHostKeyChecking=accept-new" $file.Local "$User@$Ip`:$($file.Remote)" 2>$null
            if ($LASTEXITCODE -eq 0) {
                Write-OK "Copiado: $(Split-Path $file.Local -Leaf)"
            }
            else {
                Write-WARN "Fallo al copiar: $(Split-Path $file.Local -Leaf)"
            }
        }
        else {
            Write-WARN "Archivo local no encontrado: $($file.Local)"
        }
    }
    
    # Corregir permisos del script bash
    Write-INFO "Dando permisos de ejecución a setup_rpi.sh..."
    ssh "$User@$Ip" "chmod +x $remoteDir/scripts/setup_rpi.sh" 2>$null
}

# ── FASE 4: Ejecutar setup en la Pi ───────────────────────────────────
if (-not $SkipSetup) {
    Write-STEP "FASE 4/5: Configurando entorno Python en la Raspberry Pi"
    Write-INFO "Esto puede tardar varios minutos en la Pi B+ (procesador lento)..."
    Write-Host ""
    Write-HOST "   Ejecutando setup_rpi.sh en la Pi..." -ForegroundColor Cyan
    Write-Host "   ─────────────────────────────────────────" -ForegroundColor DarkGray
    
    # Ejecutar el script de setup interactivamente
    ssh -t -o "StrictHostKeyChecking=accept-new" "$User@$Ip" "/home/pi/Rpi_Pantalla_V1/scripts/setup_rpi.sh"
    
    Write-OK "Configuración completada"
}
else {
    Write-STEP "FASE 4/5: Saltando configuración (--SkipSetup)"
}

# ── FASE 5: Verificar el despliegue ───────────────────────────────────
Write-STEP "FASE 5/5: Verificando el despliegue"

Write-INFO "Verificando que el backend responde en http://$Ip`:8000/health ..."
Start-Sleep -Seconds 2

try {
    $response = Invoke-RestMethod -Uri "http://$Ip`:8000/health" -TimeoutSec 10 -ErrorAction Stop
    if ($response.status -eq "ok") {
        Write-OK "¡Backend funcionando correctamente!"
        Write-Host ""
        Write-Host "   URL Health:  http://$Ip`:8000/health" -ForegroundColor Green
        Write-Host "   API Docs:    http://$Ip`:8000/docs" -ForegroundColor Green
    }
    else {
        Write-WARN "Backend responde pero con estado inesperado: $($response | ConvertTo-Json)"
    }
}
catch {
    Write-WARN "No se pudo verificar el backend vía HTTP."
    Write-INFO "Revisa manualmente conectándote por SSH:"
    Write-HOST "   ssh $User@$Ip" -ForegroundColor Yellow
    Write-HOST "   cat /tmp/hmi_backend.log" -ForegroundColor Yellow
    Write-HOST "   curl http://localhost:8000/health" -ForegroundColor Yellow
}

# ── Resumen final ─────────────────────────────────────────────────────
Write-Host ""
Write-Host "╔══════════════════════════════════════════════════════════════╗" -ForegroundColor Green
Write-Host "║   Despliegue completado                                      ║" -ForegroundColor Green
Write-Host "╠══════════════════════════════════════════════════════════════╣" -ForegroundColor Green
Write-Host "║   Raspberry Pi:  $($Ip.PadRight(38))║" -ForegroundColor Green
Write-Host "║   Backend:       http://$Ip`:8000/health".PadRight(54) + "║" -ForegroundColor Green
Write-Host "║   API Docs:      http://$Ip`:8000/docs".PadRight(54) + "║" -ForegroundColor Green
Write-Host "║   SSH:           ssh $User@$Ip".PadRight(54) + "║" -ForegroundColor Green
Write-Host "╚══════════════════════════════════════════════════════════════╝" -ForegroundColor Green
Write-Host ""
Write-INFO "Para detener el backend: ssh $User@$Ip 'kill `$(cat /tmp/hmi_backend.pid)'"
Write-Host ""
