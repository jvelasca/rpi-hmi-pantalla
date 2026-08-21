# Handoff RS_B_SEQUENCE — Deteccion de gaps de secuencia WebSocket por-topic (frontend)

## Resultado
Completado. La deteccion de gaps de secuencia WebSocket en el frontend ya no
compara el `sequence` global contra un unico `lastSequence` escalar. Ahora se
trackea POR-TOPIC y el gap se detecta contra la marca de agua global (maximo
`sequence` visto en cualquier topico rastreable). Esto elimina los `resync()`
innecesarios causados por gaps APARENTES: un `led_changed seq=12` tras
`led_changed seq=10` NO dispara resync si `button_pressed seq=11` fue consumido
por el topico "button". Solo se dispara resync cuando un numero de secuencia
jamas llego por ningun topico (gap real).

## Archivos modificados
- `frontend/src/hooks/sequenceTracker.ts` — [nuevo] modulo puro `createSequenceTracker()`
  + `topicForMessageType()`. Mantiene `Map<topic, lastSequence>` y expone `track()`
  (devuelve `true` si hay gap real) y `reset()`. Sin dependencias de `WebSocket`,
  testable sin entorno real.
- `frontend/src/hooks/useWebSocket.ts` — [editado] sustituye `lastSequence` escalar por
  `createSequenceTracker()`; llama `tracker.track(msg.type, msg.sequence)` en `onmessage`,
  `tracker.reset()` en `onopen` y tras `resync()` exitoso. Docstring actualizado.
- `frontend/src/tests/useWebSocket.sequence.test.ts` — [nuevo] tests Vitest de la funcion pura.
- `backend/app/api/ws.py` — [editado] SOLO docstring de modulo: nota de que `sequence` es
  global y los clientes deben detectar gaps por-topic. Sin cambios de logica.

## Verificacion ejecutada
Desde `frontend/`:

- `npm run test` -> **26 passed** (3 test files), exit 0.
  ```
  Test Files  3 passed (3)
       Tests  26 passed (26)
  ```
- `npm run build` -> **verde** (tsc -b + vite build OK), exit 0.
  ```
  ✓ 101 modules transformed.
  ✓ built in 696ms
  ```

Desde la raiz:

- `python -m ruff check backend/` -> **All checks passed!**, exit 0.

## Decisiones tomadas
- La deteccion se implementa con una **marca de agua global** derivada del mapa
  por-topic, no con una comparacion ingenua `actual > ultimo_del_topic + 1`. Razon:
  con `sequence` GLOBAL, dos eventos consecutivos del MISMO topico pueden saltar
  varios numeros (los intermedios pertenecen a otros topicos). Comparar solo contra
  el ultimo del mismo topico seguiria marcando `led 10 -> led 12` como gap aun cuando
  `button 11` ya se recibio. La marca de agua global (`sequence > globalMax + 1`)
  distingue el gap real (numero nunca visto) del aparente (numero visto en otro topico).
- La logica se extrajo a un modulo puro co-localizado (`sequenceTracker.ts`) en vez de
  dejarla inline en el hook, para poder testearla sin instanciar un `WebSocket` real.
- `status_update` y `error` no se rastrean (`topicForMessageType` devuelve `null`);
  tampoco los mensajes con `sequence: null`.

## Riesgos / pendientes
- LIMITACION CONOCIDA (no es objeto de este workstream): si el backend entrega mensajes
  de DISTINTOS topicos fuera de orden global (reordenamiento cross-topic por las colas
  async por-topico), un numero alto que llegue antes que uno intermedio mas bajo aun puede
  disparar un resync espurio. Este arreglo cubre el caso especificado (gap aparente por
  topicos), no el reordenamiento temporal entre topicos.
- Para un cliente suscrito a un SUBCONJUNTO de topicos (p. ej. solo "led"), un salto
  `led 10 -> led 12` sin recibir `button 11` seguira pareciendo un gap: con un sequence
  global no se puede distinguir "led 11 perdido" de "11 era de otro topico" sin conocer el
  mapeo sequence->topic. El frontend actual se suscribe a todos los topicos, por lo que
  no se ve afectado.
- No se ha modificado ningun contrato de tipos en `frontend/src/types/api.ts` ni
  `frontend/src/schemas/ws.ts`; `App.tsx`, `useApi.ts` y `useConnectionMonitor.ts`
  quedan intactos (pertenecen a otro subagente).

## Texto de paso al siguiente agente
RS_B_SEQUENCE completo y verificado (26 tests frontend verdes, build verde, ruff limpio).
La deteccion de gaps en `useWebSocket.ts` ahora delega en `createSequenceTracker()`
(`frontend/src/hooks/sequenceTracker.ts`), que trackea por topic y detecta el gap contra la
marca de agua global. No tocar el backend (secuencia global intacta). Pendiente opcional:
evaluar si se quiere mitigar el reordenamiento cross-topic en el futuro (p. ej. un pequeno
debounce de resync o un buffer de reordenamiento), fuera del alcance de este workstream.
