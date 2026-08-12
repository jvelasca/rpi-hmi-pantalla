# HANDOFF — Chat 3: Fase C — Bugs de Concurrencia WebSocket

> **Precondición:** Chats 1 y 2 completados
> **Salida esperada:** `docs/handoffs/CHAT_3_C_RESULTADO.md` + texto de handoff para Chat 4
> **Duración estimada:** 15-20 min

---

## Contexto

El `StateManager` implementa un contador `_sequence` para ordenar mensajes WebSocket, pero
tiene una race condition: en `set_led()`, `press_button()` y `release_button()`, la variable
`seq = self._sequence` se captura **fuera** del `with self._lock`, lo que significa que otro
hilo puede incrementar el sequence entre que se sale del lock y se usa `seq`.

Además, `set_display()` **nunca incrementa** `self._sequence`, por lo que los eventos de
display pueden compartir número de secuencia con eventos de LED o botón.

---

## TAREA 1: `set_led()` — capturar `seq` dentro del lock

**Archivo:** `backend/app/services/state_manager.py`

**Líneas actuales (164-198):**

```164:198:backend/app/services/state_manager.py
    def set_led(self, state: bool) -> LedState:
        """Establece el estado del LED y notifica.

        Args:
            state: True para encender, False para apagar.

        Returns:
            Nuevo LedState.
        """
        label = "ENCENDIDO" if state else "APAGADO"
        with self._lock:
            self._sequence += 1
            self._led_state = LedState(state=state, label=label, gpio_pin=self._led_state.gpio_pin)

        # Notificar a la HAL para actualizar GPIO fisico
        if self._updater_callback:
            try:
                self._updater_callback("led", self._led_state)
            except Exception:
                logger.exception("Error en callback GPIO para LED")

        # Persistir
        self._persist_led(state)

        # Broadcast async con sequence
        seq = self._sequence
        msg = ServerMessage(
            type="led_changed",
            data=self._led_state.model_dump(),
            sequence=seq,
        )
        self._schedule_broadcast(msg)
        self._log_event("led_" + ("on" if state else "off"), {"gpio_pin": self._led_state.gpio_pin})
        logger.info("LED -> %s (seq=%d)", label, self._sequence)
        return self._led_state
```

**Cambiar a** (mover `seq = self._sequence` dentro del `with self._lock`):

```python
    def set_led(self, state: bool) -> LedState:
        """Establece el estado del LED y notifica.

        Args:
            state: True para encender, False para apagar.

        Returns:
            Nuevo LedState.
        """
        label = "ENCENDIDO" if state else "APAGADO"
        with self._lock:
            self._sequence += 1
            self._led_state = LedState(state=state, label=label, gpio_pin=self._led_state.gpio_pin)
            seq = self._sequence

        # Notificar a la HAL para actualizar GPIO fisico
        if self._updater_callback:
            try:
                self._updater_callback("led", self._led_state)
            except Exception:
                logger.exception("Error en callback GPIO para LED")

        # Persistir
        self._persist_led(state)

        # Broadcast async con sequence
        msg = ServerMessage(
            type="led_changed",
            data=self._led_state.model_dump(),
            sequence=seq,
        )
        self._schedule_broadcast(msg)
        self._log_event("led_" + ("on" if state else "off"), {"gpio_pin": self._led_state.gpio_pin})
        logger.info("LED -> %s (seq=%d)", label, seq)
        return self._led_state
```

Nota: también cambiar `self._sequence` por `seq` en el último `logger.info()`.

---

## TAREA 2: `press_button()` — capturar `seq` dentro del lock

**Líneas actuales (208-229):**

```208:229:backend/app/services/state_manager.py
    def press_button(self) -> ButtonState:
        """Registra una pulsacion del boton.

        Returns:
            ButtonState actualizado.
        """
        with self._lock:
            self._sequence += 1
            count = self._button_state.press_count + 1
            self._button_state = ButtonState(
                pressed=True,
                press_count=count,
            )
        # Persistir
        self._persist_button(count)

        seq = self._sequence
        msg = ServerMessage(type="button_pressed", data=self._button_state.model_dump(), sequence=seq)
        self._schedule_broadcast(msg)
        self._log_event("button_pressed", {"count": count})
        logger.info("Boton presionado (count=%d, seq=%d)", count, self._sequence)
        return self._button_state
```

**Cambiar a** (mover `seq` y `count` dentro del lock):

```python
    def press_button(self) -> ButtonState:
        """Registra una pulsacion del boton.

        Returns:
            ButtonState actualizado.
        """
        with self._lock:
            self._sequence += 1
            count = self._button_state.press_count + 1
            self._button_state = ButtonState(
                pressed=True,
                press_count=count,
            )
            seq = self._sequence

        # Persistir
        self._persist_button(count)

        msg = ServerMessage(type="button_pressed", data=self._button_state.model_dump(), sequence=seq)
        self._schedule_broadcast(msg)
        self._log_event("button_pressed", {"count": count})
        logger.info("Boton presionado (count=%d, seq=%d)", count, seq)
        return self._button_state
```

---

## TAREA 3: `release_button()` — capturar `seq` dentro del lock

**Líneas actuales (231-247):**

```231:247:backend/app/services/state_manager.py
    def release_button(self) -> ButtonState:
        """Libera el boton.

        Returns:
            ButtonState actualizado.
        """
        with self._lock:
            self._sequence += 1
            self._button_state = ButtonState(
                pressed=False,
                press_count=self._button_state.press_count,
            )
        seq = self._sequence
        msg = ServerMessage(type="button_released", data=self._button_state.model_dump(), sequence=seq)
        self._schedule_broadcast(msg)
        logger.info("Boton liberado (seq=%d)", seq)
        return self._button_state
```

**Cambiar a:**

```python
    def release_button(self) -> ButtonState:
        """Libera el boton.

        Returns:
            ButtonState actualizado.
        """
        with self._lock:
            self._sequence += 1
            self._button_state = ButtonState(
                pressed=False,
                press_count=self._button_state.press_count,
            )
            seq = self._sequence

        msg = ServerMessage(type="button_released", data=self._button_state.model_dump(), sequence=seq)
        self._schedule_broadcast(msg)
        logger.info("Boton liberado (seq=%d)", seq)
        return self._button_state
```

---

## TAREA 4: `set_display()` — añadir incremento de sequence

**Líneas actuales (249-265):**

```249:265:backend/app/services/state_manager.py
    def set_display(self, connected: bool, resolution: str = "480x320", driver: str = "ili9486") -> None:
        """Actualiza la informacion del display fisico.

        Args:
            connected: True si el display esta funcional.
            resolution: Resolucion WxH.
            driver: Nombre del driver kernel.
        """
        with self._lock:
            self._display_info = DisplayInfo(
                connected=connected,
                resolution=resolution,
                driver=driver,
            )
        msg = ServerMessage(type="display_changed", data=self._display_info.model_dump(), sequence=self._sequence)
        self._schedule_broadcast(msg)
        logger.info("Display: connected=%s, %s, %s", connected, resolution, driver)
```

**Cambiar a:**

```python
    def set_display(self, connected: bool, resolution: str = "480x320", driver: str = "ili9486") -> None:
        """Actualiza la informacion del display fisico.

        Args:
            connected: True si el display esta funcional.
            resolution: Resolucion WxH.
            driver: Nombre del driver kernel.
        """
        with self._lock:
            self._sequence += 1
            self._display_info = DisplayInfo(
                connected=connected,
                resolution=resolution,
                driver=driver,
            )
            seq = self._sequence

        msg = ServerMessage(type="display_changed", data=self._display_info.model_dump(), sequence=seq)
        self._schedule_broadcast(msg)
        logger.info("Display: connected=%s, %s, %s (seq=%d)", connected, resolution, driver, seq)
```

---

## Resumen de cambios en `state_manager.py`

| Método | Línea original | Cambio |
|--------|---------------|--------|
| `set_led()` | 175-176 | Mover `seq` dentro del lock; usar `seq` en log |
| `press_button()` | 214-216, 224 | Mover `seq` y `count` dentro del lock |
| `release_button()` | 237-238, 243 | Mover `seq` dentro del lock |
| `set_display()` | 257-258, 263 | Añadir `self._sequence += 1` y capturar `seq` dentro del lock |

---

## VERIFICACIÓN

```bash
# 1. Verificar que seq se captura dentro del lock en los 4 métodos
grep -A 12 "def set_led" backend/app/services/state_manager.py | grep "seq = self._sequence"
# Debe aparecer DENTRO del bloque with self._lock (después de with, antes de la línea en blanco que cierra)

# 2. Verificar que set_display incrementa sequence
grep -A 10 "def set_display" backend/app/services/state_manager.py | grep "self._sequence += 1"
# Debe aparecer

# 3. Compilación
python -m py_compile backend/app/services/state_manager.py

# 4. Ejecutar tests existentes
python -m pytest backend/tests/test_state_manager.py -v
```

---

## AL FINALIZAR

Crea `docs/handoffs/CHAT_3_C_RESULTADO.md` con resumen de cambios y verificación.

Copia este texto de **handoff para Chat 4**:

```
[HANDOFF CHAT 3 → CHAT 4]

Chat 3 (Fase C - Concurrencia WebSocket) completado.

Cambios realizados:
- state_manager.py: set_led() — seq capturado dentro del lock (línea 177)
- state_manager.py: press_button() — seq y count capturados dentro del lock (líneas 217-218)
- state_manager.py: release_button() — seq capturado dentro del lock (línea 243)
- state_manager.py: set_display() — añadido self._sequence += 1 y seq capturado dentro del lock

Estado: Sequence numbers del WebSocket ahora son thread-safe y monotónicos.

Tarea para Chat 4 (Fase D - Hardening de Seguridad):
1. Feature-gate para admin routers (ENABLE_ADMIN_API)
2. Validar ADMIN_API_KEY en startup (rechazar claves por defecto)
3. .env.example con advertencias

Documento de referencia: docs/handoffs/CHAT_4_D_SEGURIDAD.md
```
