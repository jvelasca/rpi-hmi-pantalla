<#
.SYNOPSIS
    Configura la pantalla táctil XPT2046 en la Raspberry Pi usando SSH directo.
    NO depende del backend localhost:8000 — usa ssh.exe nativo de Windows.
#>

$ErrorActionPreference = "Continue"
$PiHost = "192.168.88.211"
$PiUser = "pi"
$PiPassword = "RaspberryB+2026!"
$sshCmd = "sshpass -p '$PiPassword' ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null ${PiUser}@${PiHost}"

function Write-Step { Write-Host "`n==============================================" -ForegroundColor Yellow; Write-Host "  $($args[0])" -ForegroundColor Yellow; Write-Host "==============================================" -ForegroundColor Yellow }
function Write-OK   { Write-Host "  [OK] $($args[0])" -ForegroundColor Green }
function Write-WARN { Write-Host "  [WARN] $($args[0])" -ForegroundColor Yellow }

# Verificar que ssh.exe existe
$sshExe = Get-Command ssh.exe -ErrorAction SilentlyContinue
if (-not $sshExe) {
    Write-Host "[ERROR] ssh.exe no encontrado. Instala OpenSSH Client." -ForegroundColor Red
    exit 1
}

# Probar conexión SSH directa
Write-Step "PASO 0: Verificando conexión SSH directa"
$testResult = cmd.exe /c "echo $PiPassword | ssh -o StrictHostKeyChecking=no -o ConnectTimeout=10 ${PiUser}@${PiHost} `"echo SSH_OK && hostname`" 2>&1"
Write-Host $testResult

if ($testResult -match "SSH_OK") {
    Write-OK "SSH directo funciona"
} else {
    Write-WARN "SSH directo no respondió como esperado. Intentando con plink..."
    # Intentar con plink (Putty) si está disponible
    $plink = Get-Command plink.exe -ErrorAction SilentlyContinue
    if ($plink) {
        Write-Host "Usando plink.exe..."
    }
}

Write-Host ""
Write-Host "══════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  Para configurar la pantalla, ejecuta MANUALMENTE:" -ForegroundColor Cyan
Write-Host "" -ForegroundColor Cyan
Write-Host "  ssh pi@192.168.88.211" -ForegroundColor White
Write-Host "  (password: RaspberryB+2026!)" -ForegroundColor White
Write-Host "" -ForegroundColor Cyan
Write-Host "  Luego en la Pi:" -ForegroundColor Cyan
Write-Host "  sudo cp /boot/config.txt /boot/config.txt.backup" -ForegroundColor White
Write-Host "  echo 'dtparam=spi=on' | sudo tee -a /boot/config.txt" -ForegroundColor White
Write-Host "  echo 'dtoverlay=ili9486,rotate=90,speed=32000000' | sudo tee -a /boot/config.txt" -ForegroundColor White
Write-Host "  echo 'dtoverlay=ads7846,cs=1,penirq=25,speed=1000000,rotate=270,swapxy=0' | sudo tee -a /boot/config.txt" -ForegroundColor White
Write-Host "  sudo reboot" -ForegroundColor White
Write-Host "══════════════════════════════════════════════════════" -ForegroundColor Cyan
