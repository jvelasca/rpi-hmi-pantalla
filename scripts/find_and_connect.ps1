<#
.SYNOPSIS
    Encuentra la Raspberry Pi en la red local y prueba la conexión SSH.

.DESCRIPTION
    Escanea la red local usando ARP y ping paralelo para localizar la
    Raspberry Pi Model B+ V1.2. Una vez encontrada, verifica que el
    puerto SSH (22) está abierto y muestra el comando para conectarse.

.PARAMETER Subnet
    Subred a escanear en formato CIDR. Si no se especifica, se detecta
    automáticamente desde la interfaz de red activa.

.PARAMETER Port
    Puerto SSH a verificar (por defecto 22).

.PARAMETER User
    Usuario SSH (por defecto "pi").

.EXAMPLE
    .\find_and_connect.ps1
    .\find_and_connect.ps1 -Subnet 192.168.1.0/24
    .\find_and_connect.ps1 -Subnet 10.0.0.0/24 -User admin
#>
[CmdletBinding()]
param(
    [string]$Subnet,
    [int]$Port = 22,
    [string]$User = "pi"
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

# ── Colores para la salida ────────────────────────────────────────────
function Write-OK   { Write-Host "  [OK] " -NoNewline -ForegroundColor Green; Write-Host $args[0] }
function Write-INFO { Write-Host " [INFO] " -NoNewline -ForegroundColor Cyan; Write-Host $args[0] }
function Write-WARN { Write-Host " [WARN] " -NoNewline -ForegroundColor Yellow; Write-Host $args[0] }
function Write-ERR  { Write-Host " [ERROR] " -NoNewline -ForegroundColor Red; Write-Host $args[0] }

Write-Host ""
Write-Host "══════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "   Raspberry Pi Finder - Rpi_Pantalla_V1" -ForegroundColor Cyan
Write-Host "══════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""

# ── 1. Detectar subred automáticamente ────────────────────────────────
if (-not $Subnet) {
    Write-INFO "Detectando subred desde la interfaz de red activa..."
    try {
        $activeAdapter = Get-NetAdapter | Where-Object { $_.Status -eq "Up" -and $_.InterfaceDescription -notmatch "Loopback|Virtual|Hyper-V|Bluetooth" } | Select-Object -First 1
        if (-not $activeAdapter) {
            throw "No se encontró ninguna interfaz de red activa."
        }
        $ipInfo = Get-NetIPAddress -InterfaceIndex $activeAdapter.InterfaceIndex -AddressFamily IPv4 | Select-Object -First 1
        if (-not $ipInfo) {
            throw "La interfaz '$($activeAdapter.Name)' no tiene dirección IPv4."
        }
        $ipParts = $ipInfo.IPAddress -split '\.'
        $Subnet = "$($ipParts[0]).$($ipParts[1]).$($ipParts[2]).0/24"
        Write-OK "Interfaz: $($activeAdapter.Name) ($($ipInfo.IPAddress))"
        Write-OK "Subred detectada: $Subnet"
    }
    catch {
        Write-ERR "No se pudo detectar la subred: $_"
        Write-INFO "Especifica la subred manualmente: .\find_and_connect.ps1 -Subnet 192.168.1.0/24"
        exit 1
    }
}

$ipPrefix = $Subnet -replace '\.\d+/\d+$'
$cidr = [int]($Subnet -replace '.*/(\d+)$', '$1')
Write-INFO "Escaneando subred: $Subnet"

# ── 2. Escaneo rápido con ping paralelo ───────────────────────────────
Write-Host ""
Write-Host "━━━ FASE 1: Escaneo de red ━━━" -ForegroundColor Yellow
Write-INFO "Enviando pings paralelos a $ipPrefix.1 - $ipPrefix.254 ..."

$jobs = @()
$startRange = 1
$endRange = 254

for ($i = $startRange; $i -le $endRange; $i++) {
    $ip = "$ipPrefix.$i"
    $jobs += Start-Job -ScriptBlock {
        param($ip)
        $result = Test-Connection -ComputerName $ip -Count 1 -Quiet -TimeoutSeconds 2
        if ($result) { $ip }
    } -ArgumentList $ip
}

# Esperar con progreso
$total = $jobs.Count
$completed = 0
$aliveIPs = @()

while ($jobs | Where-Object { $_.State -eq "Running" }) {
    $completed = ($jobs | Where-Object { $_.State -ne "Running" }).Count
    $pct = [math]::Round($completed / $total * 100, 0)
    Write-Progress -Activity "Escaneando red..." -Status "$completed de $total hosts escaneados" -PercentComplete $pct
    Start-Sleep -Milliseconds 200
}
Write-Progress -Activity "Escaneando red..." -Completed

# Recoger resultados
foreach ($job in $jobs) {
    $result = Receive-Job -Job $job -ErrorAction SilentlyContinue
    if ($result) {
        $aliveIPs += $result
    }
    Remove-Job -Job $job -Force
}

Write-INFO "Hosts activos encontrados: $($aliveIPs.Count)"

if ($aliveIPs.Count -eq 0) {
    Write-ERR "No se encontró ningún host activo en la subred $Subnet."
    Write-INFO "Verifica que:"
    Write-INFO "  1. La Raspberry Pi está encendida (LED verde fijo)"
    Write-INFO "  2. El cable Ethernet está conectado (LEDs del puerto Ethernet parpadeando)"
    Write-INFO "  3. La Pi y este PC están en la misma red"
    exit 1
}

# ── 3. Identificar Raspberry Pi entre hosts activos ───────────────────
Write-Host ""
Write-Host "━━━ FASE 2: Identificando Raspberry Pi ━━━" -ForegroundColor Yellow
Write-INFO "Buscando hostname 'raspberrypi' o similar entre $($aliveIPs.Count) hosts..."

$foundPis = @()
foreach ($ip in $aliveIPs) {
    try {
        $hostname = [System.Net.Dns]::GetHostEntry($ip).HostName.ToLower()
        if ($hostname -match "raspberry|rasp|rpi|pi\b") {
            Write-OK "¡POSIBLE RASPBERRY PI! IP: $ip  →  Hostname: $hostname"
            $foundPis += [PSCustomObject]@{ IP = $ip; Hostname = $hostname }
        }
    }
    catch {
        # No se pudo resolver hostname, probar puerto SSH directamente
    }
}

# Si no se encontró por hostname, probar SSH en todos los hosts activos
if ($foundPis.Count -eq 0) {
    Write-WARN "No se encontró Raspberry Pi por hostname. Probando puerto SSH ($Port) en todos los hosts..."
    foreach ($ip in $aliveIPs) {
        Write-INFO "Probando SSH en $ip ..."
        $tcp = New-Object System.Net.Sockets.TcpClient
        try {
            $tcp.ConnectAsync($ip, $Port).Wait(1000)
            if ($tcp.Connected) {
                Write-OK "SSH disponible en $ip — ¡Probablemente es la Raspberry Pi!"
                # Intentar obtener banner SSH
                $foundPis += [PSCustomObject]@{ IP = $ip; Hostname = "desconocido" }
            }
            $tcp.Close()
        }
        catch {
            # No disponible
        }
    }
}

if ($foundPis.Count -eq 0) {
    Write-ERR "No se encontró ninguna Raspberry Pi (ni hostname ni puerto SSH abierto)."
    Write-HOST ""
    Write-INFO "Lista de hosts activos encontrados:"
    foreach ($ip in $aliveIPs) {
        Write-Host "       $ip"
    }
    Write-Host ""
    Write-INFO "Si sabes la IP de la Pi, conéctate manualmente:"
    Write-Host "       ssh pi@<IP>" -ForegroundColor White
    exit 1
}

# ── 4. Mostrar resultados y probar conexión SSH ───────────────────────
Write-Host ""
Write-Host "━━━ FASE 3: Resultados ━━━" -ForegroundColor Yellow

if ($foundPis.Count -eq 1) {
    $target = $foundPis[0]
    Write-OK "Raspberry Pi encontrada: $($target.IP) ($($target.Hostname))"
}
else {
    Write-INFO "Se encontraron $($foundPis.Count) posibles Raspberry Pi:"
    for ($i = 0; $i -lt $foundPis.Count; $i++) {
        Write-Host "  [$i] $($foundPis[$i].IP) — $($foundPis[$i].Hostname)"
    }
    $choice = Read-Host "Selecciona el número de la Raspberry Pi correcta"
    $target = $foundPis[[int]$choice]
}

# ── 5. Mostrar comando de conexión ────────────────────────────────────
Write-Host ""
Write-Host "══════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "   Raspberry Pi localizada en: $($target.IP)" -ForegroundColor Green
Write-Host "══════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""
Write-Host "Para conectarte por SSH, ejecuta:" -ForegroundColor White
Write-Host ""
Write-Host "   ssh $User@$($target.IP)" -ForegroundColor Yellow
Write-Host ""
Write-Host "Contraseña: definida en variable de entorno RPI_PASSWORD" -ForegroundColor DarkGray
Write-Host "  (configúrala con: `$env:RPI_PASSWORD='tu_contraseña')" -ForegroundColor DarkGray
Write-Host ""

# Exportar variables para otros scripts
$env:RPI_IP = $target.IP
$env:RPI_USER = $User

# Guardar en archivo de configuración para uso posterior
$configPath = Join-Path $PSScriptRoot ".rpi_connection.json"
@{ IP = $target.IP; User = $User; Hostname = $target.Hostname; FoundAt = (Get-Date).ToString("o") } | ConvertTo-Json | Set-Content $configPath -Encoding UTF8
Write-INFO "Configuración guardada en: $configPath"

Write-Host ""
Write-Host "¿Quieres probar la conexión SSH ahora? (s/n)" -ForegroundColor Yellow
$response = Read-Host
if ($response -eq "s" -or $response -eq "S") {
    Write-INFO "Conectando... (usa 'exit' para salir)"
    Write-Host ""
    ssh "$User@$($target.IP)"
}

return @{ IP = $target.IP; User = $User }
