# Handoff B — Seguridad de red (SECURITY_MODE) + README + sudoers

## Resultado
Completado. Se cerró la brecha de seguridad por la que `POST /api/network/static` y
`POST /api/network/dhcp` eran públicos en un servidor que escucha en `0.0.0.0:8000`
(cualquiera en la LAN podía cambiar la IP y dejar la Pi inaccesible).

- Nueva dependencia reutilizable `require_admin_api_key` en `deps.py` que replica el
  patrón de `_verify_api_key` de `ssh.py`/`deploy.py` (`secrets.compare_digest`) y lo
  hace condicional a `SECURITY_MODE`.
- `SECURITY_MODE=local|protected` añadido a `config.py` (default `local`), con
  validación en `model_post_init` (`logger.critical` si `protected` sin `admin_api_key`).
- `POST /api/network/static` y `POST /api/network/dhcp` ahora exigen `X-API-Key` en modo
  `protected`. `GET /api/network` queda **público** (solo lectura de estado).
- `README.md` corregido: LED es virtual (no GPIO17); GPIO17 es la IRQ del touch.
- `config/sudoers.d/rpi-hmi` creado con regla mínima `pi → /usr/bin/nmcli`.

pytest verde (220 passed, 2 skipped) y mypy verde (0 errores).

## Archivos modificados
- [nuevo] `backend/app/api/deps.py` — dependencia `require_admin_api_key`.
- [editado] `backend/app/config.py` — `SECURITY_MODE` (`Literal["local","protected"]`,
  default `local`) + chequeo `logger.critical` en `model_post_init`; import de `Literal`.
- [editado] `backend/app/api/network.py` — `POST /static` y `POST /dhcp` con
  `dependencies=[Depends(require_admin_api_key)]`; docstrings/documentación de seguridad.
- [editado] `README.md` — tabla de hardware (LED virtual, GPIO17 = IRQ touch) + nota de aviso.
- [nuevo] `config/sudoers.d/rpi-hmi` — regla mínima para `pi`.

No se tocaron `backend/app/api/ssh.py` ni `backend/app/api/deploy.py` (refactor a
`require_admin_api_key` queda como trabajo futuro).

## Verificación ejecutada
- `python -m pytest backend/tests/ -q` (desde la raíz) → **220 passed, 2 skipped** en 83.69s.
  El `RuntimeWarning` de `state_manager.py:113` (corrutina AsyncMock no await) es preexistente.
- `cd backend && python -m mypy app/ --config-file pyproject.toml` → **`Success: no issues found in 24 source files`** (0 errores).
- `ReadLints` sobre `deps.py`, `network.py`, `config.py` → sin errores.

## Decisiones tomadas
1. **`GET /api/network` se deja público a propósito**: solo lee estado (interfaz, IP,
   modo, gateway, DNS) y no muta nada; bloquearlo rompería el panel de control sin
   aportar seguridad. Solo los mutadores exigen auth. Documentado en el docstring del módulo.
2. **No se movió `/api/network/*` a `/admin/network/*`** (opción descartada en el prompt).
   Se mantiene la ruta y se protege vía `SECURITY_MODE`, lo más simple y consistente con
   `ENABLE_ADMIN_API` sin romper el frontend/SolidJS que consume `/api/network`.
3. **La dependencia es un no-op en `local`** (retorna `None`), de modo que el HMI doméstico
   sigue funcionando sin header. En `protected`, si `admin_api_key` está vacía o no coincide,
   lanza `HTTPException(401)` (no 503), porque un endpoint de mutación protegido sin key
   configurada debe fallar cerrado con 401.
4. **`ssh.py`/`deploy.py` NO se refactorizaron** para usar `require_admin_api_key`: queda como
   trabajo futuro para evitar un diff amplio y arriesgado fuera del alcance de B.
5. **Sudoers mínimo**: `pi ALL=(root) NOPASSWD: /usr/bin/nmcli` (solo `nmcli`, nada de `ALL`).
   La ruta `/usr/bin/nmcli` es la de Raspberry Pi OS Bookworm (verificar con `which nmcli`).

## Riesgos / pendientes
- **`SECURITY_MODE=protected` no cubre aún `/admin/ssh/*` ni `/admin/deploy/*`**: siguen con
  su `_verify_api_key` propio (requieren `admin_api_key` siempre, independiente de
  `SECURITY_MODE`, y lanzan 503 si falta). Consolidar ambos en `require_admin_api_key` es
  trabajo futuro.
- **`GET /api/network` público** puede filtrar detalles de red (IP, gateway, DNS) a la LAN.
  Aceptado como trade-off deliberado; si se endurece, protegerlo en `protected` es trivial.
- **Sudoers requiere instalación manual en la Pi** (ver Texto de paso). Sin esa regla,
  `NetworkService` seguirá fallando al ejecutar `sudo nmcli` (el servicio corre como `pi`).
- El `RuntimeWarning` de pytest es preexistente (no introducido aquí).
- La dependencia usa `settings.security_mode` (atributo Python en minúscula); el env var
  es `SECURITY_MODE` (pydantic-settings con `case_sensitive=False` mapea ambos sentidos).

## Texto de paso al siguiente agente
B está completo y en verde. Para desplegar el cambio de seguridad en la Pi:

1. **Configurar `.env`** en producción:
   ```
   SECURITY_MODE=protected
   ADMIN_API_KEY=<clave de 32+ chars: python -c "import secrets; print(secrets.token_urlsafe(32))">
   ```
2. **Instalar la regla sudoers** (en la Pi, como root):
   ```bash
   sudo install -m 0440 config/sudoers.d/rpi-hmi /etc/sudoers.d/
   sudo visudo -c
   ```
   Verificar con `which nmcli` que la ruta coincide (`/usr/bin/nmcli`); si difiere, ajustar la regla.
3. **Validación rápida**:
   ```bash
   # Sin header → 401 en protected
   curl -s -o /dev/null -w "%{http_code}" -X POST http://<PI>:8000/api/network/dhcp
   # Con header → 200 (o 400 si nmcli no aplica)
   curl -s -o /dev/null -w "%{http_code}" -X POST -H "X-API-Key: <clave>" http://<PI>:8000/api/network/dhcp
   # GET público → 200
   curl -s -o /dev/null -w "%{http_code}" http://<PI>:8000/api/network
   ```

Pendiente para el orquestador: consolidar `_verify_api_key` de `ssh.py`/`deploy.py` en
`require_admin_api_key` (trabajo futuro) y que el subagente F (`docs/SECURITY.md`) documente
el modelo `local|protected`.
