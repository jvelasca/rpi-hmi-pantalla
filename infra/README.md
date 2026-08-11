Raspberry HMI - Infra
=====================

Guía rápida para crear un entorno seguro y reproducible en Python antes
de instalar paquetes en la Raspberry Pi o en un equipo de desarrollo.

Principios:
- No usar `sudo pip install`.
- Crear un entorno virtual (venv) por proyecto.
- Mantener requirements.txt o pyproject.toml y usar `pip install -e .`.

Ejemplo rápido (POSIX):

python3 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
pip install -r backend/requirements.txt

Windows (PowerShell):

python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
pip install -r backend/requirements.txt

No editar /boot/config.txt hasta que el diagnóstico indique un cambio
concreto: modelo de pantalla, controlador y wiring deben estar claros.
