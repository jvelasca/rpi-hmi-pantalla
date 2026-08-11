#!/bin/bash
set -e
echo '[1/4] Creando venv...'
python3 -m venv /home/pi/rpi_hmi/venv --clear

echo '[2/4] Activando...'
source /home/pi/rpi_hmi/venv/bin/activate

echo '[3/4] Instalando dependencias (piwheels)...'
pip install --no-cache-dir fastapi uvicorn pydantic pydantic-settings websockets

echo '[4/4] Verificando...'
python3 -c 'import fastapi, uvicorn, pydantic, websockets; print("OK fastapi=" + fastapi.__version__ + " uvicorn=" + uvicorn.__version__ + " pydantic=" + pydantic.__version__)'
echo 'DONE'
