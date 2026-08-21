# PREMISAS ESENCIALES — Gobernanza del cierre de V1

> Documento de gobernanza. Toda la ejecución de refactorización/corrección del
> proyecto **debe** respetar estas premisas. Ningún subagente puede saltárselas.
>
> Fecha: 2026-08-20 · Versión del proyecto: 0.3.1 · Estado: V1 no en producción

---

## 1. Ejecución mediante subagentes

- Todos los cambios de código se ejecutan lanzando **subagentes** (agentes de
  trabajo autónomos), nunca directamente desde el agente orquestador.
- Motivo: preservar el contexto del orquestador y aislar el riesgo de cada cambio.
- Cada subagente recibe una **tarea acotada y autocontenida**: objetivo, alcance
  (archivos), lo que NO debe tocar, criterios de aceptación y el documento de
  handoff de entrada si aplica.
- Un subagente NO mezcla fases. Si detecta un problema fuera de su alcance, lo
  documenta y no lo corrige.

## 2. Minimización de riesgo y aprobación del usuario

- Ningún cambio se aplica sin **aprobación explícita del usuario**.
- El orquestador presenta el plan (fases, archivos, impacto) y espera OK antes de
  lanzar subagentes.
- Los cambios son **pequeños, revisables y reversibles** (un tema por subagente).
- Antes de cada fase se registra un **baseline verificable** (tests verdes, estado
  git limpio, versión concreta) para poder detectar regresiones de forma inequívoca.

## 3. Control de saturación de contexto (chats/agentes)

- El trabajo se divide en **fases/chats independientes** para no saturar el
  contexto de un único agente.
- Regla de oro: un chat termina cuando su contexto está a punto de llenarse o su
  fase está completa; **nunca** se sigue acumulando trabajo a ciegas.
- El orquestador no lanza subagentes en cascada sin revisar el resultado de cada uno.

## 4. Handoffs con riesgo de alucinación = 0

- Cada fase produce un **documento de cierre** en `docs/` que contiene:
  1. **Qué se hizo** (resumen factual).
  2. **Archivos modificados/creados/eliminados** (lista exacta).
  3. **Estado de verificación** (tests, lint, build: verde/rojo + números).
  4. **Decisiones tomadas** y su justificación.
  5. **Pendientes / fuera de alcance** detectados.
  6. **Texto de paso** (bloque listo para pegar en el siguiente chat) con el
     estado de finalización, para que el siguiente agente arranque con datos
     verificados y no invente nada.
- El siguiente chat **lee el handoff antes de actuar** y lo usa como fuente de
  verdad; no infiere el estado desde memoria.

## 5. Documentación y docstrings

- Todo cambio se documenta en `/docs` donde corresponda (arquitectura, seguridad,
  estado de despliegue, runbook, contexto).
- Todo módulo/función/clase nuevo o modificado lleva **docstrings** coherentes con
  el estilo ya existente (Google-style en español).
- La documentación se actualiza **en el mismo cambio** que el código, no después.

## 6. Verificación con tests / scripts

- Para cada cambio se crean o actualizan **tests** (pytest backend/display, vitest
  frontend) y/o **scripts de verificación** reproducibles.
- Ninguna fase se da por cerrada sin su verificación ejecutada y documentada.
- Los gates globales son: `pytest`, `ruff`, `mypy`, `bandit`, `pip-audit`,
  `npm test`, `npm run build`, `npm audit`.

## 7. Libertad de refactorización (preservando la idea del proyecto)

- La app **no está en producción**, por lo que puede refactorizarse lo necesario.
- Constante inviolable: se mantiene la **idea del proyecto** — un HMI de Raspberry
  Pi con backend FastAPI único, display físico Pygame (DRM/KMS) y panel web
  SolidJS, con fuente única de verdad de hardware en `devices.yaml` y persistencia
  SQLite para estado.

## 8. Limpieza de código obsoleto y documentos antiguos

- Se elimina (o archiva en `docs/archive/` si tiene valor histórico) todo código y
  documentación obsoleta que ya no refleje el estado real del proyecto.
- Antes de eliminar se verifica que nada lo importa/referencia (grep + tests + CI).

---

## Plantilla de documento de cierre (handoff)

```markdown
# FASE <X> — <título> — CIERRE

- Rama/base: <ref git>
- Versión: <0.3.x>
- Resumen: <1-2 líneas>

## Cambios
- <archivo> — <qué cambió>

## Verificación
- pytest: N passed / F failed
- ruff / mypy / bandit / pip-audit: <verde/rojo>
- vitest / build / npm audit: <verde/rojo>

## Decisiones
- <decisión y por qué>

## Pendientes / fuera de alcance
- <lista>

## TEXTO DE PASO (pegar en el siguiente chat)
"Proyecto en <commit>. Fase <X> completada. Se hicieron <resumen>.
 Archivos: <lista>. Tests: <resultado>. Pendientes: <lista>.
 Siguiente fase: <Y> con alcance <...>. Lee <handoff> para el detalle."
```
