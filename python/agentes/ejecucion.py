"""Agente de ejecución: traduce órdenes aprobadas a mensajes para el EA."""
import logging

from python.agentes.base import Agente, OrdenAprobada
from python.config import settings

log = logging.getLogger("ejecucion")


class AgenteEjecucion(Agente):
    nombre = "ejecucion"

    def __init__(self, servidor):
        self.servidor = servidor

    def procesar(self, o: OrdenAprobada, **identidad) -> None:
        if not settings.MODO_DEMO:
            log.error("MODO_DEMO desactivado: orden NO enviada (protección)")
            return None
        log.info("Enviando orden %s %s lote=%.2f sl=%s tp=%s",
                 o.lado, o.simbolo, o.lote, o.sl, o.tp)
        self.servidor.enviar_orden(simbolo=o.simbolo, lado=o.lado,
                                   lote=o.lote, sl=o.sl, tp=o.tp, **identidad)
        return None
