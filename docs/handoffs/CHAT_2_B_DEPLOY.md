# HANDOFF — Chat 2: Fase B — Corrección del Flujo de Deploy

> **Precondición:** Chat 1 completado (versión unificada a 0.3.0, repo limpio)
> **Salida esperada:** `docs/handoffs/CHAT_2_B_RESULTADO.md` + texto de handoff para Chat 3
> **Duración estimada:** 45-60 min

---

## Contexto

El proyecto tiene múltiples mecanismos de deploy coexistiendo: `scripts/deploy.py`,
`DeployService`, `deploy_frontend.py`, `setup_rpi.sh`, `full_deploy.ps1`. El flujo
principal (`scripts/deploy.py`) tiene dos bugs críticos:

1. **No reinicia el backend tras copiar código nuevo** — el proceso antiguo sigue ejecutándose
2. **Peor aún:** llama a `ensure_backend()` ANTES del deploy, arrancando el backend viejo
   que luego nunca se reemplaza
3. **No integra el frontend** — solo despliega backend y display, el frontend va por un canal
   paralelo (`deploy_frontend.py`)

Además, `setup_rpi.sh` y `infra/INSTALL_RASPBIAN_B_PLUS.md` usan la arquitectura antigua
(`/home/pi/Rpi_Pantalla_V1/.venv`) en lugar de la nueva (`/home/pi/rpi_hmi/venv`).

---

## TAREA 1: Corregir `scripts/deploy.py` — flujo principal

### 1a. Eliminar `ensure_backend()` del flujo por defecto

Actualmente el flujo (líneas 401-415) es:

```401:415:scripts/deploy.py
        # Default: deploy + verify
        step("ENSURE BACKEND")
        ensure_backend(ssh)

        step("DEPLOY FILES (Backend)")
        deploy_svc.deploy_app(project_root=str(ROOT))
        step("DEPLOY FILES (Display)")
        deploy_display_files(ssh)
        deploy_scripts(ssh)

        step("INSTALL DEPS")
        install_display_deps(ssh)

        step("VERIFY")
        verify(ssh)
```

**Cambiar a** (nuevo orden: deploy → restart backend → wait ready → verify):

```python
        # Default: deploy + restart + verify
        step("DEPLOY FILES (Backend)")
        deploy_svc.deploy_app(project_root=str(ROOT))
        step("DEPLOY FILES (Display)")
        deploy_display_files(ssh)
        deploy_scripts(ssh)

        step("DEPLOY FRONTEND (Static)")
        _deploy_frontend_static(ssh, ROOT)

        step("INSTALL DEPS")
        install_display_deps(ssh)

        step("RESTART BACKEND (apply new code)")
        deploy_svc.restart_backend()
        print("  Esperando /health/ready...")
        for i in range(30):
            if check_backend_ready(ssh):
                print("  Backend ready tras reinicio")
                break
            time.sleep(1)
        else:
            print("  [WARN] Backend no respondió /health/ready en 30s")

        step("RESTART DISPLAY")
        ssh.execute("sudo systemctl restart rpi-hmi-display.service 2>&1 || echo 'not running'", timeout=10)

        step("VERIFY")
        verify(ssh)
```

### 1b. Añadir función `_deploy_frontend_static()`

Añade esta función antes de `main()` (por ejemplo, después de `deploy_scripts()` en línea 143):

```python
def _deploy_frontend_static(ssh: ParamikoSSHDriver, project_root: Path) -> None:
    """Build y deploy del frontend a backend/app/static/."""
    import subprocess

    frontend_dir = project_root / "frontend"
    dist_dir = frontend_dir / "dist"
    static_remote = f"{PI_BASE}/backend/app/static"

    # Build frontend si es necesario
    if not (dist_dir / "index.html").exists():
        print("  Construyendo frontend (npm run build)...")
        result = subprocess.run(
            ["npm", "run", "build"],
            cwd=str(frontend_dir),
            capture_output=True, text=True,
            timeout=120,
        )
        if result.returncode != 0:
            print(f"  [WARN] Build frontend falló: {result.stderr[:200]}")
            return
        print("  Frontend built OK")

    # Crear directorio remoto
    ssh.execute(f"mkdir -p {static_remote}", timeout=10)

    # Copiar archivos de dist/ a backend/app/static/
    count = 0
    for local_file in dist_dir.rglob("*"):
        if local_file.is_dir():
            continue
        rel = str(local_file.relative_to(dist_dir)).replace("\\", "/")
        remote = f"{static_remote}/{rel}"
        # Asegurar subdirectorio remoto
        remote_parent = str(Path(remote).parent)
        if rel != Path(remote).name:
            ssh.execute(f"mkdir -p {remote_parent}", timeout=10)
        try:
            ssh.transfer_file(str(local_file), remote)
            count += 1
            print(f"  OK  static/{rel} ({local_file.stat().st_size}B)")
        except Exception as exc:
            print(f"  ERR static/{rel}: {exc}")
    print(f"  Total: {count} static files deployed")
```

Necesitarás importar `subprocess` al principio del archivo.

### 1c. Corregir flujo `--install-service`

Líneas 378-388 actualmente hacen deploy, deps, y luego instalan servicios pero **no reinician**:

```378:388:scripts/deploy.py
        if args.install_service:
            step("DEPLOY BACKEND")
            deploy_svc.deploy_app(project_root=str(ROOT))
            step("DEPLOY DISPLAY FILES")
            deploy_display_files(ssh)
            deploy_scripts(ssh)
            step("INSTALL DEPS")
            install_display_deps(ssh)
            step("INSTALL SYSTEMD SERVICES")
            install_services(ssh)
            return
```

**Cambiar a** (añadir restart y health check al final, y frontend):

```python
        if args.install_service:
            step("DEPLOY BACKEND")
            deploy_svc.deploy_app(project_root=str(ROOT))
            step("DEPLOY DISPLAY FILES")
            deploy_display_files(ssh)
            deploy_scripts(ssh)
            step("DEPLOY FRONTEND (Static)")
            _deploy_frontend_static(ssh, ROOT)
            step("INSTALL DEPS")
            install_display_deps(ssh)
            step("INSTALL SYSTEMD SERVICES")
            install_services(ssh)
            step("RESTART BACKEND (apply new code)")
            deploy_svc.restart_backend()
            print("  Esperando /health/ready...")
            for i in range(30):
                if check_backend_ready(ssh):
                    print("  Backend ready")
                    break
                time.sleep(1)
            return
```

### 1d. Corregir flujo `--hmi`

Líneas 390-399: mismo problema, no integra frontend ni reinicia. Añadir:

```python
            step("DEPLOY FRONTEND (Static)")
            _deploy_frontend_static(ssh, ROOT)
```

después de `deploy_scripts(ssh)` en la línea 395, y antes de `install_display_deps`. También
añadir un `deploy_svc.restart_backend()` antes de `run_hmi(ssh)`.

---

## TAREA 2: Ampliar `DeployService.deploy_app()` para frontend

**Archivo:** `backend/app/services/deploy_service.py`

### 2a. Ampliar `DEPLOY_DIRECTORIES`

Añadir `"frontend/dist"` a la lista:

```46:53:backend/app/services/deploy_service.py
DEPLOY_DIRECTORIES = [
    "backend/app",
    "backend/config",
    "backend/tests",
    "display",
    "config/systemd",
    "scripts",
]
```

**Cambiar a:**

```python
DEPLOY_DIRECTORIES = [
    "backend/app",
    "backend/config",
    "backend/tests",
    "display",
    "config/systemd",
    "scripts",
    "frontend/dist",
]
```

### 2b. Ampliar extensiones permitidas

```336:336:backend/app/services/deploy_service.py
        allowed_extensions = {".py", ".yaml", ".yml", ".json", ".toml", ".txt", ".sh", ".service"}
```

**Cambiar a:**

```python
        allowed_extensions = {".py", ".yaml", ".yml", ".json", ".toml", ".txt", ".sh", ".service", ".js", ".css", ".html", ".svg", ".ico", ".woff2"}
```

---

## TAREA 3: Actualizar `scripts/setup_rpi.sh`

### 3a. Cambiar `PROJECT_DIR`

```124:124:scripts/setup_rpi.sh
PROJECT_DIR="/home/pi/Rpi_Pantalla_V1"
```

**Cambiar a:**

```bash
PROJECT_DIR="/home/pi/rpi_hmi"
```

### 3b. Cambiar `VENV_DIR`

```141:141:scripts/setup_rpi.sh
VENV_DIR="$PROJECT_DIR/.venv"
```

**Cambiar a:**

```bash
VENV_DIR="$PROJECT_DIR/venv"
```

### 3c. Revisar y actualizar todas las referencias

Busca y reemplaza en el archivo:
- `Rpi_Pantalla_V1` → `rpi_hmi` (en mensajes/echo también)
- `.venv` → `venv` (en referencias a rutas)
- El comando `nohup` de la línea 218 debería cambiarse por `systemctl start`:

```218:218:scripts/setup_rpi.sh
nohup python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 > /tmp/hmi_backend.log 2>&1 &
```

**Cambiar a:**

```bash
sudo systemctl start rpi-hmi-backend.service 2>/dev/null || \
    nohup python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 > /tmp/hmi_backend.log 2>&1 &
```

---

## TAREA 4: Actualizar `infra/INSTALL_RASPBIAN_B_PLUS.md`

Hay que actualizar TODAS las referencias obsoletas en este archivo. Los cambios principales:

### 4a. Cambiar `hmi-backend.service` → `rpi-hmi-backend.service`

Línea ~398: El nombre del servicio systemd:

```
sudo nano /etc/systemd/system/hmi-backend.service
```

Cambiar a:

```
sudo nano /etc/systemd/system/rpi-hmi-backend.service
```

Y en toda mención a `hmi-backend.service`.

### 4b. Cambiar rutas de proyecto

- `/home/pi/Rpi_Pantalla_V1` → `/home/pi/rpi_hmi` (líneas ~295, ~345, ~411)
- `.venv` → `venv` (líneas ~298, ~345, ~412)

### 4c. Actualizar FASE 10 completa (systemd)

La sección de systemd (líneas ~393-438) usa la arquitectura antigua completa. Reemplazar
el contenido del servicio por:

```ini
[Unit]
Description=RPi HMI Backend (FastAPI)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=pi
Group=pi
WorkingDirectory=/home/pi/rpi_hmi
ExecStart=/home/pi/rpi_hmi/venv/bin/python3 -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Y añadir mención al servicio display:
```
sudo systemctl enable rpi-hmi-backend.service rpi-hmi-display.service
```

### 4d. Actualizar FASE 7 (clonar proyecto)

Cambiar URL de clone y rutas (líneas ~290-310).

---

## VERIFICACIÓN

```bash
# 1. Deploy.py ya no llama a ensure_backend() antes de deploy
grep -n "ensure_backend" scripts/deploy.py
# Debe aparecer solo en la definición, no en el flujo default

# 2. Deploy.py llama a restart_backend() después de deploy
grep -n "restart_backend" scripts/deploy.py
# Debe aparecer en el flujo default

# 3. DeployService incluye frontend
grep "frontend" backend/app/services/deploy_service.py
# Debe mostrar frontend en DEPLOY_DIRECTORIES

# 4. setup_rpi.sh usa rutas nuevas
grep "Rpi_Pantalla_V1" scripts/setup_rpi.sh
# SOLO debe aparecer en el título/banner, no en PROJECT_DIR

# 5. INSTALL_RASPBIAN usa nombres nuevos
grep "hmi-backend" infra/INSTALL_RASPBIAN_B_PLUS.md
# Debe devolver vacío (debe usar rpi-hmi-backend)

# 6. Python syntax check
python -m py_compile scripts/deploy.py
python -m py_compile backend/app/services/deploy_service.py
```

---

## AL FINALIZAR

Crea `docs/handoffs/CHAT_2_B_RESULTADO.md` con:
1. Resumen de cambios
2. Resultado de verificación
3. Incidencias

Y copia este texto de **handoff para Chat 3**:

```
[HANDOFF CHAT 2 → CHAT 3]

Chat 2 (Fase B - Deploy) completado.

Cambios realizados:
- scripts/deploy.py: flujo reordenado a deploy → restart → health. ensure_backend() ya no se
  llama antes del deploy. Se añadió restart_backend() + espera /health/ready + restart display.
- scripts/deploy.py: nueva función _deploy_frontend_static() que compila el frontend con
  npm run build y copia dist/ a backend/app/static/ en la Pi.
- DeployService: DEPLOY_DIRECTORIES ahora incluye frontend/dist. Extensiones permitidas
  ampliadas con .js, .css, .html, .svg, .ico, .woff2.
- scripts/setup_rpi.sh: rutas actualizadas a /home/pi/rpi_hmi y venv/. nohup reemplazado
  por systemctl start.
- infra/INSTALL_RASPBIAN_B_PLUS.md: nombres de servicios y rutas actualizados a nueva
  arquitectura.

Estado: Deploy funcional. Frontend integrado. Arquitectura unificada.

Tarea para Chat 3 (Fase C - Concurrencia WebSocket):
1. state_manager.py set_led(): mover seq = self._sequence dentro del lock
2. state_manager.py press_button(): mover seq = self._sequence dentro del lock
3. state_manager.py release_button(): mover seq = self._sequence dentro del lock
4. state_manager.py set_display(): añadir self._sequence += 1

Documento de referencia: docs/handoffs/CHAT_3_C_CONCURRENCIA.md
```
