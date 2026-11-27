"""Coordina el riesgo y los envíos de dos procesos sobre la misma cuenta demo."""
from contextlib import contextmanager
import json
import os

from python.agentes.riesgo import riesgo_disponible


@contextmanager
def bloqueo(path):
    with path.open("a+b") as handle:
        handle.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            yield False
        else:
            # Al cerrar el descriptor se libera el bloqueo incluso si hay una excepción.
            yield True


class ControlDemo:
    def __init__(self, estado, compartido=None):
        self.shared = compartido is not None
        self.directory = compartido if self.shared else estado
        self.directory.mkdir(parents=True, exist_ok=True)
        self.pending = self.directory / "orden_compartida.json"

    def riesgo(self, account):
        with bloqueo(self.directory / "riesgo.lock") as acquired:
            return acquired and riesgo_disponible(account, self.directory)

    @contextmanager
    def entrada(self):
        with bloqueo(self.directory / "envio.lock") as acquired:
            yield acquired and not self.pending.exists()

    def enviar(self, terminal, orden):
        if not self.shared:
            return terminal.order_send(orden)
        with self.pending.open("x", encoding="utf-8") as file:
            json.dump(orden, file)
            file.flush()
            os.fsync(file.fileno())
        result = terminal.order_send(orden)
        if result is not None and result.retcode not in (
            terminal.TRADE_RETCODE_TIMEOUT, terminal.TRADE_RETCODE_CONNECTION,
            terminal.TRADE_RETCODE_PLACED,
        ):
            self.pending.unlink()
        return result
