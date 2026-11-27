"""Orquestador: Análisis -> Señal -> Riesgo -> Ejecución.

Uso:
    python -m python.orquestador
"""
import logging
from pathlib import Path
from uuid import uuid4

from python.agentes.analisis import AgenteAnalisis
from python.agentes.ejecucion import AgenteEjecucion
from python.agentes.senal import AgenteSenal
from python.agentes.riesgo import riesgo_disponible
from python.comunicacion.servidor_zmq import ServidorZMQ
from python.comunicacion.cuenta_mt5 import CuentaMT5
from python.config import settings

log = logging.getLogger("orquestador")


class Orquestador:
    def __init__(self, servidor=None, cuenta=None, estado_dir=Path("logs")):
        self.servidor = servidor or ServidorZMQ()
        self.cuenta = cuenta or CuentaMT5()
        self.estado_dir = Path(estado_dir)
        self.analisis = AgenteAnalisis()
        self.senal = AgenteSenal()
        self.ejecucion = AgenteEjecucion(self.servidor)
        self.servidor.on_dato = self.on_dato
        self.servidor.on_respuesta = self.on_respuesta

    def on_dato(self, msg: dict) -> None:
        if (msg["tipo"] != "vela" or msg.get("timeframe") != settings.TIMEFRAME
                or msg.get("simbolo") not in settings.SIMBOLOS_BROKER.values()):
            return
        a = self.analisis.procesar(msg)
        if a is None:
            return
        s = self.senal.procesar(a)
        if s is None:
            return
        log.info("Señal %s %s (%s)", s.lado, s.simbolo, s.motivo)
        if not settings.MODO_DEMO:
            return
        try:
            lectura = self.cuenta.snapshot()
            if lectura is None:
                return
            cuenta, posiciones, pendientes = lectura
            if not self.riesgo_disponible(cuenta):
                return
            ocupadas = (*posiciones, *pendientes)
            if (len(ocupadas) >= settings.MAX_POSICIONES_ABIERTAS
                    or any(p.symbol == s.simbolo for p in ocupadas)
                    or self.servidor.orden_en_curso):
                return
            orden = self.cuenta.preparar(s, cuenta.equity)
        except (OSError, ImportError, ValueError, KeyError):
            log.exception("Entrada bloqueada: no se pudo verificar la cuenta o el riesgo")
            return
        if orden is not None:
            self.ejecucion.procesar(orden, solicitud=uuid4().hex, cuenta=cuenta.login,
                                   servidor=cuenta.server)

    def riesgo_disponible(self, cuenta):
        return riesgo_disponible(cuenta, self.estado_dir)

    def on_respuesta(self, msg: dict) -> None:
        log.info("Orden %s: ok=%s ticket=%s volumen=%s retcode=%s",
                 msg["solicitud"], msg["ok"], msg["ticket"], msg.get("volumen"),
                 msg.get("retcode"))

    def ejecutar(self) -> None:
        self.servidor.ejecutar()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    Orquestador().ejecutar()
