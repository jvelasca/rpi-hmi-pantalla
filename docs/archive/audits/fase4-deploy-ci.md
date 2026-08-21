# FASE 4 — Deploy/CI: GitHub Actions, rollback, artefactos ✅ COMPLETADA

**Fecha:** 2026-08-11
**Tests:** 116/116 pasando (sin cambios en tests existentes)
**Resultado:** CI pipeline con 4 jobs (tests, lint, type-check, frontend), release automático por tags, rollback con snapshots versionados, VERSION canónico

---

## Cambios realizados

### 1. 🟡 GitHub Actions — CI pipeline (`.github/workflows/ci.yml`)

Workflow que se ejecuta en cada push/PR a `main`. Cuatro jobs paralelos:

| Job | Descripción | Triggers |
|-----|-------------|----------|
| **Tests** | Matrix Python 3.11 + 3.12. Instala SDL2 (pygame), backend + display deps, ejecuta `pytest backend/tests/ display/tests/` | Push/PR a main |
| **Lint (ruff)** | `ruff check backend/ display/ scripts/` con config de `backend/pyproject.toml` | Push/PR a main |
| **Type check (mypy)** | `mypy app/` desde `backend/` con strict mode | Push/PR a main |
| **Frontend build** | `npm ci` + `npm run build` (TypeScript + Vite), sube `frontend/dist/` como artifact | Push/PR a main |

**Características:**
- `fail-fast: false` en la matrix de tests (un fallo no cancela otras versiones)
- `concurrency` configurada para cancelar runs redundantes en el mismo PR
- Artifact del frontend retenido 7 días
- Cache de pip y npm para builds rápidos

### 2. 🟡 Release workflow (`.github/workflows/release.yml`)

Disparado al pushear tags `v*` (ej. `v0.2.0`):

| Job | Descripción |
|-----|-------------|
| **test** | Ejecuta tests (bloqueante, el release no procede si fallan) |
| **release** | Construye frontend, empaqueta proyecto completo en `rpi-hmi-vX.Y.Z.tar.gz`, crea GitHub Release con `softprops/action-gh-release` |

**Artefacto del release:**
- `rpi-hmi-vX.Y.Z.tar.gz` — archivo completo con backend, display, frontend compilado, config, scripts, VERSION, README, LICENSE
- Release notes generadas automáticamente desde los commits

### 3. 🟡 Rollback con snapshots versionados (`scripts/rollback.py`)

Sistema de backup/restore para deployments en la Raspberry Pi:

| Comando | Acción |
|---------|--------|
| `--backup` | Crea snapshot tar.gz con timestamp + metadatos de versión en `/home/pi/rpi_hmi_backups/` |
| `--list` | Lista backups disponibles con tamaño, fecha y versión |
| `--restore` | Restaura el último backup (o uno específico). Crea backup de seguridad previo. |
| `--clean N` | Elimina backups antiguos, conserva solo los últimos N |

**Características de seguridad:**
- Antes de restaurar, para los servicios systemd (`rpi-hmi-backend`, `rpi-hmi-display`)
- Crea backup de seguridad (`PRE_ROLLBACK_*`) del estado actual antes de restaurar
- Si la extracción falla, reporta el error e indica dónde está el backup de seguridad
- Metadatos en `.meta` con versión y timestamp

**Uso típico:**
```bash
# Antes de un deploy
python scripts/rollback.py --backup

# Desplegar
python scripts/deploy.py --hmi

# Si algo falla, restaurar
python scripts/rollback.py --restore
```

### 4. 🟡 Archivo `VERSION` canónico

- `VERSION` en la raíz del proyecto: `0.2.0`
- Coincide con `backend/pyproject.toml` version
- Usado por el release workflow para nombrar el artefacto
- El deploy puede escribir `.deploy_version` en la Pi para tracking

---

## Archivos creados (5)

| Archivo | Propósito |
|---------|----------|
| `.github/workflows/ci.yml` | CI: tests, lint, mypy, frontend build |
| `.github/workflows/release.yml` | Release automático por tag semántico |
| `scripts/rollback.py` | Backup/restore de deployments en la Pi |
| `VERSION` | Versión canónica del proyecto (`0.2.0`) |
| `docs/audits/fase4-deploy-ci.md` | Este documento |

---

## Archivos modificados (0)

Ningún archivo existente fue modificado. Todos los cambios son adiciones nuevas.

---

## Verificación

- `python -m pytest backend/tests/ display/tests/ -v --tb=short` → **116 passed**
- Sin regresiones: los 116 tests existentes pasan sin cambios
- Los workflows se validarán en el primer push a GitHub
- La release y el rollback requieren acceso SSH a la Pi para funcionar

---

## Próxima fase: FASE 5 — Calidad

**Prompt para el siguiente chat:**

> Continuamos el plan de trabajo consolidado para el proyecto Rpi_Pantalla_V1 (Raspberry Pi HMI).
>
> Las FASE 0 (Seguridad), FASE 1 (Arquitectura), FASE 2 (Estado/eventos), FASE 3 (Display) y FASE 4 (Deploy/CI) están completadas — 116/116 tests pasando.
> Los documentos de cierre están en:
> - `docs/audits/fase0-seguridad.md`
> - `docs/audits/fase1-arquitectura.md`
> - `docs/audits/fase2-estado-eventos.md`
> - `docs/audits/fase3-display.md`
> - `docs/audits/fase4-deploy-ci.md`
> - `docs/audits/plan-consolidado.md`
>
> Ahora ejecuta la FASE 5 — Calidad: tests de integración, cobertura real, frontend.
> Revisa `docs/audits/plan-consolidado.md` para los detalles de la fase.
>
> IMPORTANTE:
> - Lee los archivos relevantes antes de modificar nada
> - Ejecuta los tests (`python -m pytest backend/tests/ -v --tb=short`) después de cada cambio
> - Si algo rompe, arréglalo antes de continuar
> - No modifiques nada que no esté en esta lista
