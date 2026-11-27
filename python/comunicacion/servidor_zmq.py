"""Servidor ZeroMQ del lado Python.

- SUB: recibe ticks/velas publicados por el EA (puerto ZMQ_PUERTO_DATOS).
- REP: responde a solicitudes del EA (puerto ZMQ_PUERTO_COMANDOS). El EA envía
  una solicitud periódica ("poll") y Python responde con la orden pendiente,
  si la hay, o con un mensaje vacío.

Uso rápido:
    python -m python.comunicacion.servidor_zmq
"""
import logging
import json
import time
from pathlib import Path

import zmq

from python.comunicacion import mensajes
from python.config import settings

log = logging.getLogger("servidor_zmq")


class ServidorZMQ:
    def __init__(self, host=settings.ZMQ_HOST,
                 puerto_datos=settings.ZMQ_PUERTO_DATOS,
                 puerto_comandos=settings.ZMQ_PUERTO_COMANDOS,
                 diario=Path("logs/orden_enviada.json")):
        self.ctx = zmq.Context.instance()
        self.sub = self.ctx.socket(zmq.SUB)
        self.sub.connect(f"tcp://{host}:{puerto_datos}")
        self.sub.setsockopt_string(zmq.SUBSCRIBE, "")
        self.rep = self.ctx.socket(zmq.REP)
        self.rep.bind(f"tcp://{host}:{puerto_comandos}")
        self.pendiente = None
        self.diario = Path(diario)
        self.enviada = json.loads(self.diario.read_text()) if self.diario.exists() else None
        self.on_dato = lambda msg: None
        self.on_respuesta = lambda msg: None

    @property
    def orden_en_curso(self):
        if self.pendiente and time.monotonic() >= self.pendiente[1]:
            self.pendiente = None
        return self.pendiente is not None or self.enviada is not None

    def enviar_orden(self, **datos) -> None:
        if self.orden_en_curso:
            return
        texto = mensajes.crear("orden", **datos)
        self.pendiente = (texto, time.monotonic() + settings.ORDEN_VIGENCIA_MS / 1000)

    def _procesar_datos(self) -> None:
        for _ in range(100):
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
        try:
            msg = mensajes.decodificar(texto)
            if msg["tipo"] == "respuesta" and msg.get("solicitud") == self.enviada:
                if self.enviada is not None:
                    self.on_respuesta(msg)
                    self.diario.unlink(missing_ok=True)
                    self.enviada = None
        except mensajes.MensajeInvalido:
            pass
        if self.orden_en_curso and self.pendiente and self.enviada is None:
            orden, _ = self.pendiente
            solicitud = json.loads(orden)["solicitud"]
            self.diario.parent.mkdir(parents=True, exist_ok=True)
            with self.diario.open("x", encoding="utf-8") as archivo:
                json.dump(solicitud, archivo)
            self.enviada = solicitud
            self.pendiente = None
            self.rep.send_string(orden)
        else:
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
