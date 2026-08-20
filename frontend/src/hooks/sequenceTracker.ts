/**
 * sequenceTracker — Deteccion de gaps de secuencia WebSocket POR-TOPIC.
 *
 * Contexto: el backend mantiene un `sequence` GLOBAL (orden total entre todos
 * los eventos) pero las colas de entrega son por-topico. Esto provoca gaps
 * APARENTES en el cliente: p. ej. un cliente recibe `led_changed seq=10` y
 * despues `led_changed seq=12`; si entre medias llega `button_pressed seq=11`,
 * ese `11` pertenece al topico "button" y NO representa un mensaje perdido de
 * "led". Comparar el sequence global (o el ultimo del topico sin mas contexto)
 * dispararia un `resync()` innecesario.
 *
 * Estrategia: se guarda el ultimo sequence POR-TOPIC (`lastByTopic`), pero la
 * deteccion de gap se evalua contra la MARCA DE AGUA GLOBAL (el maximo sequence
 * visto en CUALQUIER topico rastreable):
 *
 *  - Si `sequence <= globalMax + 1`, todos los numeros intermedios ya fueron
 *    vistos en algun topico (o este es el siguiente esperado) => no hay gap.
 *    Esto absorbe los "huecos" aparentes entre dos eventos del mismo topico
 *    cuando los numeros intermedios pertenecen a otros topicos.
 *  - Si `sequence > globalMax + 1`, existe al menos un numero de secuencia que
 *    nunca llego por NINGUN topico => gap real (mensaje perdido) => resync.
 */

export type SequenceTopic = "led" | "button" | "display";

/** Devuelve el topic rastreable de un tipo de mensaje, o null si no se rastrea. */
export function topicForMessageType(type: string): SequenceTopic | null {
  switch (type) {
    case "led_changed":
      return "led";
    case "button_pressed":
    case "button_released":
      return "button";
    case "display_changed":
    case "display_command":
    case "display_settings_changed":
      return "display";
    default:
      return null;
  }
}

export interface SequenceTracker {
  /**
   * Evalua si hay un gap real de secuencia y registra el sequence como baseline
   * del topic. Devuelve `true` si hay gap (el hook activara un `resync`);
   * `false` en caso contrario, o si el mensaje no tiene sequence numerico o
   * topic rastreable.
   *
   * En caso de gap NO se actualiza el baseline (el hook activa un resync que
   * reseteara el mapa completo).
   */
  track(type: string, sequence: number | null): boolean;
  /** Resetea todos los baselines (onopen / tras un resync exitoso). */
  reset(): void;
}

export function createSequenceTracker(): SequenceTracker {
  const lastByTopic = new Map<SequenceTopic, number>();

  return {
    track(type, sequence) {
      const topic = topicForMessageType(type);
      if (topic === null || typeof sequence !== "number") {
        return false;
      }

      // Marca de agua global: maximo sequence visto en cualquier topic.
      let globalMax: number | null = null;
      for (const value of lastByTopic.values()) {
        if (globalMax === null || value > globalMax) {
          globalMax = value;
        }
      }

      // Primer mensaje rastreable: establece el baseline sin gap.
      if (globalMax === null) {
        lastByTopic.set(topic, sequence);
        return false;
      }

      // Salto por encima de la marca de agua global => al menos un sequence
      // nunca llego por ningun topic => gap real.
      if (sequence > globalMax + 1) {
        return true;
      }

      // No hay gap: actualizamos solo el ultimo del topic actual.
      lastByTopic.set(topic, sequence);
      return false;
    },
    reset() {
      lastByTopic.clear();
    },
  };
}
