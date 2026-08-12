# Plan de Trabajo Consolidado — Rpi_Pantalla_V1

Consenso de 3 auditorías independientes (propia + 2 externas).

---

## Resumen de fases

| Fase | Estado | Objetivo |
|------|--------|----------|
| 🔴 FASE 0 | ✅ COMPLETADA | Seguridad: credenciales, CORS, auth, systemd |
| 🟠 FASE 1 | ✅ COMPLETADA | Arquitectura: unificar HAL, limpiar legacy, devices.yaml |
| 🟠 FASE 2 | ✅ COMPLETADA | Estado/eventos: corregir ws_count, uptime, versionar WS |
| 🟠 FASE 3 | ✅ COMPLETADA | Display: thread-safety, rendimiento, touch robusto |
| 🟠 FASE 3.5 | ✅ COMPLETADA | Corrección P0/P1: credenciales, WS display, contrato TS, HAL unificada |
| 🟡 FASE 4 | ✅ COMPLETADA | Deploy/CI: GitHub Actions, rollback, artefactos |
| 🟢 FASE 5 | ✅ COMPLETADA | Calidad: tests integración, cobertura real, frontend |
| 🟢 FASE 6 | ✅ COMPLETADA | Persistencia: SQLite, health check, tipos OpenAPI |

---

## Problemas críticos resueltos en FASE 0

| # | Issue | Severidad | Estado |
|---|-------|-----------|--------|
| 1 | Contraseña hardcodeada en `scripts/deploy.py` | 🔴 CRÍTICO | ✅ Corregido |
| 2 | `.env` con credenciales reales | 🔴 CRÍTICO | ✅ Vaciado |
| 3 | `GET /api/ssh/exec?cmd=...` RCE remoto | 🔴 CRÍTICO | ✅ Eliminado |
| 4 | CORS `*` + `allow_credentials=True` | 🟠 ALTO | ✅ Cerrado |
| 5 | Sin autenticación en endpoints admin | 🟠 ALTO | ✅ API key |
| 6 | `AutoAddPolicy()` SSH | 🟡 MEDIO | ✅ WarningPolicy |
| 7 | Display como `User=root` | 🔴 CRÍTICO | ✅ User=pi |
| 8 | `/docs` expuesto en producción | 🟠 ALTO | ✅ ENABLE_DOCS |

---

## Problemas resueltos en FASE 1

| # | Issue | Severidad | Estado |
|---|-------|-----------|--------|
| 1 | Código legacy disperso en raíz y `hardware/` | 🟡 MEDIO | ✅ Archivado en `legacy/` |
| 2 | Dos HAL GPIO coexistiendo (`hal.py` + `gpio_service.py`) | 🟠 ALTO | ✅ Unificada en `gpio_service.py` |
| 3 | GPIO pin 17 hardcodeado en 3 sitios (`LedState`, `main.py`, `StateManager`) | 🟠 ALTO | ✅ Cargado desde `devices.yaml` |
| 4 | Dos entry points con lógica duplicada | 🟡 MEDIO | ✅ `backend/app/main.py` canónico |
| 5 | Lógica SSH/SFTP duplicada entre `scripts/deploy.py` y `DeployService` | 🟡 MEDIO | ✅ `deploy.py` usa `DeployService` |

---

## Próximos pasos

Ejecutar las fases en orden secuencial, cada una en un chat independiente.
Ver `docs/audits/fase3-display.md` para el prompt de la FASE 4.
