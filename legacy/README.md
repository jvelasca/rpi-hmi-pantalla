# Código Legacy

Este directorio contiene código histórico del proyecto Rpi_Pantalla_V1
que fue reemplazado por la arquitectura unificada actual.

## Archivos

| Archivo | Descripción | Razón de archivado |
|---------|-------------|-------------------|
| `pi_hmi_server.py` | Servidor HMI ligero sin dependencias (stdlib) | Reemplazado por `backend/app/main.py` (FastAPI) |
| `fb_ui.py` | UI directa sobre framebuffer | Reemplazado por `display/` (pygame/KMS/DRM) |
| `fb_test.py` | Test de patrón para framebuffer | Código de diagnóstico inicial, reemplazado por `diagnostics/` |
| `hal.py` | HAL GPIO alternativa con `load_devices()` | Unificada con `backend/app/services/gpio_service.py` |

## Notas

- Estos archivos **no** se importan desde el código actual.
- Se conservan como referencia histórica del desarrollo iterativo.
- No modificar sin evaluar migración a la nueva arquitectura.
