"""Orquestador: Análisis -> Señal -> Riesgo -> Ejecución.

Uso:
    python -m python.orquestador
"""
import logging

from python.agentes.analisis import AgenteAnalisis
from python.agentes.ejecucion import AgenteEjecucion
from python.agentes.riesgo import AgenteRiesgo
from python.agentes.senal import AgenteSenal
from python.comunicacion.servidor_zmq import ServidorZMQ

log = logging.getLogger("orquestador")


class Orquestador:
    def __init__(self, servidor=None):
        self.servidor = servidor or ServidorZMQ()
        self.analisis = AgenteAnalisis()
        self.senal = AgenteSenal()
        self.riesgo = AgenteRiesgo()
        self.ejecucion = AgenteEjecucion(self.servidor)
        self.servidor.on_dato = self.on_dato
        self.servidor.on_respuesta = self.on_respuesta

    def on_dato(self, msg: dict) -> None:
        if msg["tipo"] != "vela":
            return
        a = self.analisis.procesar(msg)
        if a is None:
            return
        s = self.senal.procesar(a)
        if s is None:
            return
        log.info("Señal %s %s (%s)", s.lado, s.simbolo, s.motivo)
        orden = self.riesgo.procesar(s)
        if orden is None:
            return
        self.riesgo.registrar_apertura(orden.simbolo)
        self.ejecucion.procesar(orden)

    def on_respuesta(self, msg: dict) -> None:
        if msg["ok"]:
            log.info("Orden ejecutada, ticket=%s", msg["ticket"])
        else:
            log.error("Orden rechazada: %s", msg["error"])

    def ejecutar(self) -> None:
        self.servidor.ejecutar()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    Orquestador().ejecutar()
