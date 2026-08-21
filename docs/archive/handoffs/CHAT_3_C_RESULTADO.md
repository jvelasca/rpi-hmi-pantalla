# Chat 3 (Fase C) — Resultado: Bugs de Concurrencia WebSocket

## Cambios realizados

### Archivo modificado: `backend/app/services/state_manager.py`

| Método | Cambio | Impacto |
|---|---|---|
| `set_led()` | `seq = self._sequence` movido dentro del `with self._lock:` (línea 177). `logger.info` usa `seq` en vez de `self._sequence`. | Elimina race condition: el valor de seq ya no puede ser incrementado por otro hilo entre el lock y su uso. |
| `press_button()` | `seq = self._sequence` movido dentro del `with self._lock:` (línea 220). `logger.info` usa `seq` en vez de `self._sequence`. | `count` y `seq` se capturan atómicamente. Sin riesgo de que otro hilo incremente sequence entre medias. |
| `release_button()` | `seq = self._sequence` movido dentro del `with self._lock:` (línea 242). | Misma corrección que `press_button`. |
| `set_display()` | Añadido `self._sequence += 1` y `seq = self._sequence` dentro del lock (líneas 257, 263). `ServerMessage` usa `seq` en vez de `self._sequence`. | Los eventos de display ahora incrementan y reportan su propio sequence number, en lugar de compartir el número con otros eventos o usar uno obsoleto. |

## Verificación

```
seq = self._sequence -> 4 ocurrencias (líneas 177, 220, 242, 263) ✓
self._sequence += 1  -> 4 ocurrencias (líneas 175, 214, 237, 257) ✓
py_compile            -> OK sin errores ✓
```

## Estado final

Los sequence numbers del WebSocket son ahora **thread-safe** (capturados bajo lock) y **monotónicos** (todos los métodos de modificación de estado incrementan el contador). Ningún mensaje WebSocket puede reportar un sequence number que haya sido alterado por otro hilo concurrente.
