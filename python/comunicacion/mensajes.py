"""Protocolo de mensajes JSON entre MT5 y Python.

Todos los mensajes llevan: tipo, version, ts (epoch ms) y datos propios.

Tipos:
  - tick      (MT5 -> Python, PUB/SUB)
  - vela      (MT5 -> Python, PUB/SUB)
  - orden     (Python -> MT5, REQ/REP)
  - respuesta (MT5 -> Python, REQ/REP)
"""
import json
import time

VERSION = 1

CAMPOS_REQUERIDOS = {
    "tick": {"simbolo", "bid", "ask"},
    "vela": {"simbolo", "timeframe", "apertura", "maximo", "minimo", "cierre", "volumen"},
    "orden": {"simbolo", "lado", "lote", "sl", "tp"},
    "respuesta": {"ok", "ticket", "error"},
}

LADOS_VALIDOS = {"BUY", "SELL", "CLOSE"}


class MensajeInvalido(ValueError):
    """El mensaje no cumple el protocolo."""


def crear(tipo: str, **datos) -> str:
    """Construye un mensaje JSON validado."""
    msg = {"tipo": tipo, "version": VERSION, "ts": int(time.time() * 1000), **datos}
    validar(msg)
    return json.dumps(msg, separators=(",", ":"))


def decodificar(texto: str) -> dict:
    """Parsea y valida un mensaje JSON recibido."""
    try:
        msg = json.loads(texto)
    except json.JSONDecodeError as e:
        raise MensajeInvalido(f"JSON inválido: {e}") from e
    validar(msg)
    return msg


def validar(msg: dict) -> None:
    if not isinstance(msg, dict):
        raise MensajeInvalido("El mensaje debe ser un objeto JSON")
    tipo = msg.get("tipo")
    if tipo not in CAMPOS_REQUERIDOS:
        raise MensajeInvalido(f"Tipo desconocido: {tipo!r}")
    if msg.get("version") != VERSION:
        raise MensajeInvalido(f"Versión no soportada: {msg.get('version')!r}")
    faltan = CAMPOS_REQUERIDOS[tipo] - msg.keys()
    if faltan:
        raise MensajeInvalido(f"Faltan campos en {tipo}: {sorted(faltan)}")
    if tipo == "orden" and msg["lado"] not in LADOS_VALIDOS:
        raise MensajeInvalido(f"Lado inválido: {msg['lado']!r}")
    if tipo == "orden" and not msg["lote"] > 0:
        raise MensajeInvalido("El lote debe ser mayor que 0")
