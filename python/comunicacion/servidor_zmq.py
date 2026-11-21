"""Servidor ZeroMQ del lado Python.

- SUB: recibe ticks/velas publicados por el EA (puerto ZMQ_PUERTO_DATOS).
- REP: responde a solicitudes del EA (puerto ZMQ_PUERTO_COMANDOS). El EA envía
  una solicitud periódica ("poll") y Python responde con la orden pendiente,
  si la hay, o con un mensaje vacío.

Uso rápido:
    python -m python.comunicacion.servidor_zmq
"""
import logging
import queue

import zmq

from python.comunicacion import mensajes
from python.config import settings

log = logging.getLogger("servidor_zmq")


class ServidorZMQ:
    def __init__(self, host=settings.ZMQ_HOST,
                 puerto_datos=settings.ZMQ_PUERTO_DATOS,
                 puerto_comandos=settings.ZMQ_PUERTO_COMANDOS):
        self.ctx = zmq.Context.instance()
        self.sub = self.ctx.socket(zmq.SUB)
        self.sub.connect(f"tcp://{host}:{puerto_datos}")
        self.sub.setsockopt_string(zmq.SUBSCRIBE, "")
        self.rep = self.ctx.socket(zmq.REP)
        self.rep.bind(f"tcp://{host}:{puerto_comandos}")
        self.ordenes_pendientes: "queue.Queue[str]" = queue.Queue()
        self.on_dato = lambda msg: None
        self.on_respuesta = lambda msg: None

    def enviar_orden(self, **datos) -> None:
        """Encola una orden validada; se entrega en el siguiente poll del EA."""
        self.ordenes_pendientes.put(mensajes.crear("orden", **datos))

    def _procesar_datos(self) -> None:
        while True:
            try:
                texto = self.sub.recv_string(flags=zmq.NOBLOCK)
            except zmq.Again:
                return
            try:
                self.on_dato(mensajes.decodificar(texto))
            except mensajes.MensajeInvalido as e:
                log.warning("Dato descartado: %s", e)

    def _procesar_comando(self) -> None:
        try:
            texto = self.rep.recv_string(flags=zmq.NOBLOCK)
        except zmq.Again:
            return
        # Si el EA reporta una respuesta de orden, la registramos.
        try:
            msg = mensajes.decodificar(texto)
            if msg["tipo"] == "respuesta":
                self.on_respuesta(msg)
        except mensajes.MensajeInvalido:
            pass  # un poll vacío ("{}") no es un error
        try:
            self.rep.send_string(self.ordenes_pendientes.get_nowait())
        except queue.Empty:
            self.rep.send_string("{}")

    def ejecutar(self) -> None:
        poller = zmq.Poller()
        poller.register(self.sub, zmq.POLLIN)
        poller.register(self.rep, zmq.POLLIN)
        log.info("Servidor ZMQ activo (modo demo=%s)", settings.MODO_DEMO)
        try:
            while True:
                eventos = dict(poller.poll(timeout=100))
                if self.sub in eventos:
                    self._procesar_datos()
                if self.rep in eventos:
                    self._procesar_comando()
        except KeyboardInterrupt:
            log.info("Servidor detenido")
        finally:
            self.sub.close()
            self.rep.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    srv = ServidorZMQ()
    srv.on_dato = lambda m: log.info("%s %s", m["tipo"], m.get("simbolo"))
    srv.ejecutar()
