# Inicio rápido para desarrolladores

## Configuración del entorno local (PC)

### Requisitos
- Python 3.8+
- pip
- virtualenv (optional, recomendado)
- Git

### Instalación (POSIX: Linux/macOS)

```bash
# 1. Clonar repositorio
git clone <repo-url>
cd Rpi_Pantalla_V1

# 2. Crear entorno virtual
python3 -m venv .venv
source .venv/bin/activate

# 3. Actualizar pip
python -m pip install -U pip

# 4. Instalar dependencias
pip install -r backend/requirements.txt

# 5. Verificar instalación
python -c "import fastapi, pydantic, gpiozero; print('OK')"

# 6. Ejecutar tests (modo mock, sin hardware)
pytest backend/tests/

# 7. Diagnosticos en modo mock
python diagnostics/run_diagnostics.py --output diagnostics/report_local

# 8. Test GPIO mock (led1 como en devices.yaml)
python diagnostics/gpio/blink_test.py led1 --times 3
```

### Instalación (Windows PowerShell)

```powershell
# 1. Clonar repositorio
git clone <repo-url>
cd Rpi_Pantalla_V1

# 2. Crear entorno virtual
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 3. Actualizar pip
python -m pip install -U pip

# 4. Instalar dependencias
pip install -r backend/requirements.txt

# 5. Tests
pytest backend/tests/

# 6. Diagnosticos
python diagnostics/run_diagnostics.py --output diagnostics/report_local

# 7. GPIO test
python diagnostics/gpio/blink_test.py led1 --times 3
```

## Desarrollo en la Raspberry Pi

**IMPORTANTE:** Lee primero `infra/INSTALL_RASPBIAN_B_PLUS.md`.

```bash
# En la Pi (SSH)
ssh pi@<IP_DE_LA_PI>

# Setup
cd /home/pi/Rpi_Pantalla_V1
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt

# Test GPIO real (LED en pin 17)
python diagnostics/gpio/blink_test.py led1 --times 5

# Iniciar servidor FastAPI
python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000

# Desde tu PC accede a: http://<IP_DE_LA_PI>:8000/health
curl http://<IP_DE_LA_PI>:8000/health
```

## Code quality

### Type checking (Python)

```bash
mypy --strict backend/
```

Ejecutar antes de commit.

### Formatting

```bash
black backend/ diagnostics/
ruff check backend/ diagnostics/
```

### Testing

```bash
pytest backend/tests/ --cov=backend/ --cov-report=html
# Abre: htmlcov/index.html en navegador
```

## Estructura de módulos

```
backend/
├── app/
│   ├── main.py              # FastAPI app
│   ├── hardware/
│   │   └── hal.py           # HAL, Device, GPIODriver, MockGPIODriver
│   ├── domain/
│   │   ├── enums.py         # (próximo: DeviceType, DeviceState, etc.)
│   │   └── exceptions.py    # (próximo: HardwareException, etc.)
│   ├── services/
│   │   └── device_manager.py # (próximo: DeviceManager)
│   └── api/
│       └── devices.py       # (próximo: endpoints)
├── config/
│   └── devices.yaml         # Device registry
└── tests/
	└── test_hal.py          # (próximo: tests)
diagnostics/
├── run_diagnostics.py       # Diagnóstico del sistema
└── gpio/
	└── blink_test.py        # Test de LED
```

## Primeros pasos de desarrollo

1. **Lee** `infra/INSTALL_RASPBIAN_B_PLUS.md` si aún no instalaste OS en la Pi
2. **Ejecuta** `pytest` localmente para asegurar que todo compila
3. **Modifica** `backend/config/devices.yaml` si cambias pines
4. **Implementa** siguiendo la estructura de carpetas (domain → application → infrastructure)
5. **Documenta** con docstrings exhaustivos (Lee los archivos existentes como referencia)
6. **Testea** en local (con MockGPIODriver) antes de tocar hardware real

## Notas finales

- **No uses `sudo pip install`** en la Pi. Siempre un venv.
- **Backupea `/boot/config.txt`** antes de cambiar overlays.
- **Documenta hardware:** ejecuta `diagnostics/run_diagnostics.py` y guarda el report.
- **Commits claros:** mensajes descriptivos, pequeños cambios lógicos.
