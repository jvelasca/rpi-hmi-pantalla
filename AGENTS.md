# AGENTS.md — Contexto del proyecto RPi HMI (anti-alucinación)

> Instrucciones de trabajo para agentes de IA. Lee este archivo al inicio de cada
> tarea y síguelo de forma imperativa. No inventes datos del proyecto.

## Fuentes de verdad (leer, no duplicar)

- `@docs/CONTEXT.md` — checkpoint de estado global. **Leer al inicio de cada sesión,
  actualizar al final.**
- `@docs/PREMISAS_ESENCIALES.md` — reglas de gobernanza (subagentes, verificación,
  handoffs). De cumplimiento obligatorio.
- `@docs/deploy/handoffs/*.md` — cierres de fase con "TEXTO DE PASO". Usa el último
  handoff como estado real de la fase anterior.

No copies el contenido completo de estos archivos en otras reglas ni en tu respuesta:
referéncialos con `@ruta` o con la ruta del archivo.

## Reglas obligatorias en cada tarea

1. **Leer contexto al inicio.** Antes de actuar, lee `docs/CONTEXT.md` y
   `docs/PREMISAS_ESENCIALES.md`. Arranca con datos verificados, no de memoria.

2. **Leer el archivo real antes de editar.** Usa `Read` sobre el fichero exacto que
   vayas a modificar o proponer. Nunca asumas su contenido desde memoria o desde un
   resumen antiguo.

3. **Verificar, no adivinar.** Si dudas de un hecho (versión, estado, contrato, conteo
   de tests, rutas), confírmalo con `git grep`, tests o linters. Nunca inventes.

4. **Trabajar vía subagentes.** Un cambio = un subagente, acotado y revisable. No
   mezcles fases ni corrijas fuera de alcance: documéntalo y no lo toques.

5. **Documentar cada cierre.** Cada fase produce un handoff en `docs/` con resumen,
   archivos tocados, verificación, decisiones, pendientes y **"TEXTO DE PASO"**
   listo para el siguiente chat.

6. **No cerrar una fase sin gates en verde.** Antes de dar por cerrada una fase,
   ejecuta y deja verde:
   - `pytest backend/tests/ display/tests/`
   - `ruff check backend/ display/ scripts/ --config backend/pyproject.toml`
   - `mypy app/` (desde `backend/`, con `--config-file backend/pyproject.toml`)
   - `bandit -r backend/app display --exclude backend/tests,display/tests -q --severity-level medium`
   - `pip-audit`
   - `npm run test`, `npm run build`, `npm audit --audit-level=high` (desde `frontend/`)

7. **Verificar versiones de forma exacta.** La versión es única y centralizada.
   Antes de tocarla, compruébala en todos los espejos:
   ```
   git grep -n "<version>" -- VERSION pyproject.toml backend/app/_version.py display/app.py frontend/package.json
   ```
   Espejos actuales: `VERSION` (raíz) → `backend/app/_version.py` (`_FALLBACK`) →
   `display/app.py` (`_load_version()`). Versión actual: **0.4.1**.

## Proyecto (resumen factual)

HMI de Raspberry Pi: backend FastAPI (`backend/`), display Pygame DRM/KMS (`display/`),
frontend SolidJS+TypeScript (`frontend/`), persistencia SQLite, servicios systemd y
gates de CI/seguridad. Versión actual: `0.4.1`.
