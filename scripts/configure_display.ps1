# configure_display.ps1 — Solo configura la pantalla (overlay + reinicio)
$ProjectRoot = "E:\SINCRONIZADO\Informatica\Proyectos VisualStudio\Python\Rapsberry\Rpi_Pantalla_V1"
$PiHost = "192.168.88.211"
$ErrorActionPreference = "Continue"

# ── Arrancar backend ───────────────────────────────────────
Write-Host "Arrancando backend..." -ForegroundColor Yellow
Get-Process -Name "python" -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -match "uvicorn" } | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep 1
Start-Job -Name "HMI" -ScriptBlock { param($r) Set-Location $r; python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 2>&1 } -ArgumentList $ProjectRoot | Out-Null
Start-Sleep 5

# ── WebClient helper ──────────────────────────────────────
$wc = New-Object System.Net.WebClient
$wc.Encoding = [System.Text.Encoding]::UTF8
$wc.Headers.Add("Content-Type", "application/json")

function GetApi($p) {
    $url = "http://localhost:8000" + $p
    return $wc.DownloadString($url)
}

function PostApi($p, $j) {
    $url = "http://localhost:8000" + $p
    return $wc.UploadString($url, "POST", $j)
}

function Ssh($cmd) {
    $esc = $cmd -replace '"','\"'
    $json = "{""command"":""$esc"",""timeout"":30}"
    return PostApi "/api/ssh/execute" $json
}

# ── Verificar backend ─────────────────────────────────────
Write-Host "Verificando backend..." -ForegroundColor Yellow
$h = GetApi "/health"
if ($h -match "ok") { Write-Host "[OK] Backend responde" -ForegroundColor Green }
else { Write-Host "[ERROR] Backend no responde: $h" -ForegroundColor Red; $wc.Dispose(); exit 1 }

# ── Conectar SSH ──────────────────────────────────────────
Write-Host "Conectando SSH..." -ForegroundColor Yellow
$conn = PostApi "/api/ssh/connect" "{""host"":""$PiHost"",""user"":""pi"",""password"":""RaspberryB+2026!"",""port"":22}"
if ($conn -match "success.*true") { Write-Host "[OK] SSH conectado" -ForegroundColor Green }
else { Write-Host "[ERROR] SSH: $conn" -ForegroundColor Red; $wc.Dispose(); exit 1 }

# ── DIAGNÓSTICO rápido ────────────────────────────────────
Write-Host "`n--- DIAGNÓSTICO ---" -ForegroundColor Cyan
$fb = Ssh "ls /dev/fb0 2>&1"
$ov = Ssh "grep -iE 'ili9486|ads7846' /boot/config.txt 2>/dev/null || echo NO"
Write-Host "fb0: $fb"
Write-Host "overlays: $ov"

$hasFB = ($fb -match "fb0")
$hasIli = ($ov -match "ili9486")
$hasOV = ($ov -match "ads7846")

# ── CONFIGURAR si falta ────────────────────────────────────
if ($hasFB -and $hasIli) {
    Write-Host "`n[OK] /dev/fb0 ya existe y overlay ili9486 presente. No se necesita configuracion." -ForegroundColor Green
} else {
    Write-Host "`n--- CONFIGURANDO PANTALLA ---" -ForegroundColor Cyan
    
    Write-Host "Backup..." -ForegroundColor Yellow
    $r1 = Ssh "sudo cp /boot/config.txt /boot/config.txt.backup 2>&1; echo DONE"
    Write-Host $r1
    
    Write-Host "Agregando spi=on..." -ForegroundColor Yellow
    $r2 = Ssh "echo dtparam=spi=on | sudo tee -a /boot/config.txt"
    Write-Host $r2
    
    Write-Host "Agregando overlay ili9486 (driver display)..." -ForegroundColor Yellow
    $r_ili = Ssh "echo dtoverlay=ili9486,rotate=90,speed=32000000 | sudo tee -a /boot/config.txt"
    Write-Host $r_ili
    
    Write-Host "Agregando overlay ads7846 (táctil)..." -ForegroundColor Yellow
    $r3 = Ssh "echo dtoverlay=ads7846,cs=1,penirq=25,speed=1000000,rotate=270,swapxy=0 | sudo tee -a /boot/config.txt"
    Write-Host $r3
    
    Write-Host "Verificando config final..." -ForegroundColor Yellow
    $r4 = Ssh "grep -iE 'ili9486|ads7846' /boot/config.txt"
    Write-Host $r4
    
    if ($r4 -match "ili9486") {
        Write-Host "[OK] Overlays agregados. REINICIANDO..." -ForegroundColor Green
        Ssh "sudo reboot" | Out-Null
        Write-Host "Esperando 100s..." -ForegroundColor Yellow
        Start-Sleep 100
        
        Write-Host "Reconectando SSH..." -ForegroundColor Yellow
        PostApi "/api/ssh/connect" "{""host"":""$PiHost"",""user"":""pi"",""password"":""RaspberryB+2026!"",""port"":22}" | Out-Null
        Start-Sleep 3
        
        Write-Host "Verificando /dev/fb0..." -ForegroundColor Yellow
        $fb2 = Ssh "ls -l /dev/fb0 2>&1"
        Write-Host $fb2
        if ($fb2 -match "fb0") {
            Write-Host "[OK] /dev/fb0 DETECTADO!" -ForegroundColor Green
            $hasFB = $true
        } else {
            Write-Host "[WARN] /dev/fb0 sigue sin aparecer" -ForegroundColor Yellow
        }
    } else {
        Write-Host "[ERROR] No se pudo agregar el overlay ili9486" -ForegroundColor Red
    }
}

# ── PRUEBA framebuffer ─────────────────────────────────────
if ($hasFB) {
    Write-Host "`n--- PRUEBA FRAMEBUFFER ---" -ForegroundColor Cyan
    Write-Host "Ruido..." -ForegroundColor Yellow
    Ssh "sudo dd if=/dev/urandom of=/dev/fb0 bs=480 count=320 2>/dev/null" | Out-Null
    Start-Sleep 1
    Write-Host "Negro..." -ForegroundColor Yellow
    Ssh "sudo dd if=/dev/zero of=/dev/fb0 bs=480 count=320 2>/dev/null" | Out-Null
    Write-Host "[OK] Prueba completada (ruido->negro)" -ForegroundColor Green
}

# ── VERIFICAR touch ─────────────────────────────────────────
Write-Host "`n--- VERIFICAR TOUCH ---" -ForegroundColor Cyan
$t1 = Ssh "ls -l /dev/input/by-path/ 2>/dev/null || ls -l /dev/input/"
Write-Host $t1
$t2 = Ssh "cat /proc/bus/input/devices 2>/dev/null | grep -iE 'Name|xpt|ads|touch' || echo SIN_DISPOSITIVOS"
Write-Host $t2

Write-Host "`n==============================================" -ForegroundColor Cyan
Write-Host "  fb0: $(if ($hasFB) {'SI'} else {'NO'})  |  Touch: $(if ($t2 -match 'xpt|ads') {'SI'} else {'NO'})" -ForegroundColor Cyan
Write-Host "==============================================" -ForegroundColor Cyan

$wc.Dispose()
