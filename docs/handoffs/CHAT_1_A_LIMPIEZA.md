# HANDOFF — Chat 1: Fase A — Limpieza y Unificación de Versión

> **Entrada:** Estado actual del repositorio (workspace completo)
> **Salida esperada:** `docs/handoffs/CHAT_1_A_RESULTADO.md` + texto de handoff para Chat 2
> **Duración estimada:** 30-45 min

---

## Contexto

Este es el **Chat 1 de 5** del plan de consolidación. El proyecto RPi HMI tiene versión
inconsistente (VERSION=0.2.0, pyproject root=0.3.0, backend=0.2.0, frontend=0.1.0) y basura
en el repositorio (frontend/Untitled, __pycache__). El objetivo de esta fase es normalizar
todo a `0.3.0` y dejar el repo limpio para las siguientes fases.

**No debes modificar nada fuera de los archivos listados aquí.** Si encuentras algo que
parezca un bug pero no está en esta lista, documéntalo en el archivo de resultado pero no lo
corrijas. Las siguientes fases se encargan del resto.

---

## TAREA 1: Eliminar `frontend/Untitled`

**Archivo:** `frontend/Untitled`

Es un archivo de 26KB que contiene una auditoría anterior. No es código, no debe estar en
el repositorio.

**Acción:** Eliminar el archivo.

```bash
# Verifica que existe
ls -la "frontend/Untitled"
# Elimínalo
rm "frontend/Untitled"
```

---

## TAREA 2: Eliminar todos los `__pycache__/` y `*.pyc`

El `.gitignore` ya los excluye, pero están físicamente en el workspace. Limpiarlos.

**Directorios con `__pycache__/` detectados (verifica que sigan existiendo):**
- `./__pycache__/`
- `backend/__pycache__/`
- `backend/app/__pycache__/`
- `backend/app/api/__pycache__/`
- `backend/app/hardware/__pycache__/`
- `backend/app/models/__pycache__/`
- `backend/app/services/__pycache__/`
- `backend/tests/__pycache__/`
- `display/__pycache__/`
- `display/ui/__pycache__/`
- `display/tests/__pycache__/`
- `diagnostics/gpio/__pycache__/`
- `.pytest_cache/` (también limpiar)

**Acción:** Usar el siguiente comando desde la raíz del proyecto:

```bash
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null
find . -type f -name "*.pyc" -delete 2>/dev/null
find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null
```

En Windows PowerShell:
```powershell
Get-ChildItem -Recurse -Directory -Filter "__pycache__" | Remove-Item -Recurse -Force
Get-ChildItem -Recurse -Filter "*.pyc" | Remove-Item -Force
Get-ChildItem -Recurse -Directory -Filter ".pytest_cache" | Remove-Item -Recurse -Force
```

Verifica después que no quede ninguno:
```bash
find . -name "*.pyc" -o -type d -name "__pycache__" | head -20
# Debe devolver vacío
```

---

## TAREA 3: Unificar versión a `0.3.0`

Hay que cambiar `0.2.0` (y `0.1.0` en frontend) a `0.3.0` en TODOS estos lugares:

### 3a. Archivo `VERSION` (raíz)

```7:7:VERSION
0.2.0
```

**Cambiar a:**

```
0.3.0
```

### 3b. `backend/pyproject.toml`

```7:7:backend/pyproject.toml
version = "0.2.0"
```

**Cambiar a:**

```toml
version = "0.3.0"
```

También en la misma línea, cambiar el clasificador:

```17:17:backend/pyproject.toml
    "Development Status :: 3 - Alpha",
```

**Cambiar a:**

```toml
    "Development Status :: 4 - Beta",
```

### 3c. `backend/app/main.py` — línea 159 (FastAPI version)

```159:159:backend/app/main.py
    version="0.2.0",
```

**Cambiar a:**

```python
    version="0.3.0",
```

### 3d. `backend/app/main.py` — línea 203 (JSON response fallback)

```203:203:backend/app/main.py
            "version": "0.2.0",
```

**Cambiar a:**

```python
            "version": "0.3.0",
```

### 3e. `frontend/package.json`

```4:4:frontend/package.json
  "version": "0.1.0",
```

**Cambiar a:**

```json
  "version": "0.3.0",
```

---

## TAREA 4: Corregir log SSH (WarningPolicy → RejectPolicy)

El código usa `paramiko.RejectPolicy()` pero el mensaje de log dice "WarningPolicy".

**Archivo:** `backend/app/services/ssh_manager.py`, línea 244

```244:244:backend/app/services/ssh_manager.py
            logger.info("Politica SSH: WarningPolicy (se advierte si la host key es desconocida)")
```

**Cambiar a:**

```python
            logger.info("Politica SSH: RejectPolicy (solo acepta claves conocidas en known_hosts)")
```

---

## TAREA 5: Actualizar README.md

Leer el README actual y actualizar:

- Referencias a la versión (deben decir `0.3.0`)
- El conteo de tests (debe ser coherente; si no se puede verificar, poner "~180+ tests" en lugar de un número exacto)
- Cualquier mención a `0.2.0` o arquitectura antigua

**Archivo:** `README.md`

Revisa el archivo completo (226 líneas) y actualiza todas las referencias a la versión.

---

## VERIFICACIÓN

Después de completar todas las tareas, verifica:

```bash
# 1. Versión unificada
cat VERSION                          # Debe decir 0.3.0
grep '"0.2.0"' backend/app/main.py   # No debe encontrar nada
grep '"0.1.0"' frontend/package.json # No debe encontrar nada
grep 'version.*0\.3\.0' backend/pyproject.toml backend/app/main.py frontend/package.json

# 2. frontend/Untitled eliminado
ls frontend/Untitled 2>&1            # Debe decir "No such file"

# 3. Sin __pycache__
find . -name "__pycache__" -o -name "*.pyc" 2>/dev/null | wc -l  # Debe ser 0

# 4. Log SSH corregido
grep "WarningPolicy" backend/app/services/ssh_manager.py  # Debe devolver vacío
grep "RejectPolicy" backend/app/services/ssh_manager.py   # Debe encontrar 2 ocurrencias
```

---

## AL FINALIZAR

Crea el archivo `docs/handoffs/CHAT_1_A_RESULTADO.md` con:

1. Resumen de cambios realizados (qué archivos se modificaron, con qué cambios)
2. Resultado de la verificación
3. Cualquier incidencia o hallazgo no previsto

Y escribe el siguiente texto de **handoff para el Chat 2** (cópialo literalmente al
inicio del Chat 2):

```
[HANDOFF CHAT 1 → CHAT 2]

Chat 1 (Fase A - Limpieza y Unificación) completado.

Cambios realizados:
- VERSION actualizado a 0.3.0
- backend/pyproject.toml actualizado a 0.3.0 (y clasificador a Beta)
- backend/app/main.py actualizado a 0.3.0 (líneas 159 y 203)
- frontend/package.json actualizado a 0.3.0
- frontend/Untitled eliminado
- Todos los __pycache__/ y *.pyc eliminados
- ssh_manager.py línea 244: log corregido de WarningPolicy a RejectPolicy
- README.md actualizado con versión 0.3.0

Estado del repo: Limpio. Versión unificada a 0.3.0.

Tarea para Chat 2 (Fase B - Deploy):
1. scripts/deploy.py: reordenar flujo a deploy → restart → health (NO ensure_backend antes)
2. DeployService: añadir frontend a DEPLOY_DIRECTORIES
3. setup_rpi.sh: actualizar PROJECT_DIR y VENV_DIR a nueva arquitectura
4. infra/INSTALL_RASPBIAN_B_PLUS.md: actualizar rutas y nombres de servicios

Documento de referencia: docs/handoffs/CHAT_2_B_DEPLOY.md
```
