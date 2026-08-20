# RS — Security Audit (Gate D3): pip-audit + bandit + npm audit

> Handoff de verificación local. NO se modifica código, tests ni docs de producto.
> Fecha: 2026-08-20

## 1. Comandos que declara el CI (`.github/workflows/ci.yml`)

Extraídos literalmente del job `security` y del job `frontend`:

| Job | Comando real | Path / alcance |
|-----|--------------|----------------|
| `security` → pip-audit | `pip-audit -r backend/requirements.txt \|\| pip-audit` | `backend/requirements.txt` (fallback: entorno instalado) |
| `security` → bandit | `bandit -r backend/app display --exclude backend/tests,display/tests -q --severity-level medium` | `backend/app` + `display` (excluye tests); bloquea solo medium+ |
| `frontend` → npm audit | `npm audit --audit-level=high` | `frontend/` (tras `npm ci`); bloquea solo high/critical |

> Nota: el CI de `bandit` NO usa `-c backend/pyproject.toml`. No existe sección `[tool.bandit]` en `backend/pyproject.toml`, por lo que bandit corre con defaults.

## 2. Entorno local usado para la verificación

- Python `3.13.7` (el CI usa 3.11/3.12; sin impacto relevante para estos checks).
- `bandit 1.9.4` (ya instalado).
- `pip-audit 2.10.1` (instalado localmente para esta tarea; tooling, no toca el repo).
- `node v22.14.0`, `npm 10.9.2`.

## 3. Resultados reales (salida pegada + exit code)

### 3.1 pip-audit — VERDE

Comando ejecutado (equivalente al del CI; `pip-audit.exe` no está en PATH):

```text
python -m pip_audit -r backend/requirements.txt
```

Salida:

```text
No known vulnerabilities found
```

Exit code: `0` (no hubo necesidad del fallback `|| pip-audit`).

### 3.2 bandit — VERDE

Comando ejecutado (idéntico al del CI, vía módulo):

```text
python -m bandit -r backend/app display --exclude backend/tests,display/tests -q --severity-level medium
```

Salida:

```text
[tester]	WARNING	nosec encountered (B104), but no failed test on file backend/app\config.py:55
```

Exit code: `0` (sin hallazgos de severidad medium ni high; solo un warning informativo de nosec).

### 3.3 npm audit — VERDE

Comando ejecutado (idéntico al del CI):

```text
npm audit --audit-level=high
```

Salida:

```text
found 0 vulnerabilities
```

Exit code: `0`.

> Caveat: se auditó contra `frontend/package-lock.json` ya versionado. No se ejecutó `npm ci` (no hay `node_modules`), lo que es equivalente para el audit del lockfile.

## 4. Tabla de hallazgos

| # | Severidad | Archivo:línea | Regla | ¿Intencional? | Acción recomendada |
|---|-----------|---------------|-------|---------------|--------------------|
| 1 | Info (no bloquea) | `backend/app/config.py:55` | bandit B104 (bind `0.0.0.0`) | Sí — `# nosec B104` | Ninguna. Es un `Field(default="0.0.0.0")` (string de config Pydantic), no un `bind()` real; por eso bandit avisa "no failed test". El `# nosec` es redundante; opcionalmente se puede dejar como documentación o retirar. |
| 2 | Suprimido (nosec) | `backend/app/services/ssh_manager.py:317` | bandit B601 (exec_command con string) | Sí — `# nosec B601` | Mantener. Es ejecución de comandos remotos de deploy (operación de confianza). Verificar que `run_command()` no reciba entrada no confiable del usuario. |
| 3 | — | `backend/requirements.txt` | pip-audit | n/a | Sin vulnerabilidades conocidas. |
| 4 | — | `frontend/package-lock.json` | npm audit | n/a | 0 vulnerabilidades. |

### Clasificación (según reglas antialucinación)

- (a) Vulnerabilidades reales de runtime: **ninguna**.
- (b) Hallazgos intencionales marcados con `# nosec`: **2** (`config.py:55` B104, `ssh_manager.py:317` B601).
- (c) Falsos positivos de dev-only: **ninguno** (el B104 es un marker sin test disparado; no es falso positivo sino nosec redundante).

## 5. Estado de cada check

- `pip-audit`: **VERDE** (exit 0)
- `bandit`: **VERDE** (exit 0, sin medium/high)
- `npm audit`: **VERDE** (exit 0)

Conclusión: el gate D3 es reproducible localmente y pasa en los tres checks.
