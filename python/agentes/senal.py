"""Agente de señal: cruce de EMAs confirmado por RSI.

BUY  cuando la EMA rápida cruza por encima de la lenta y RSI < RSI_MAX_COMPRA.
SELL cuando la EMA rápida cruza por debajo de la lenta y RSI > RSI_MIN_VENTA.
"""
from typing import Optional

from python.agentes.base import Agente, Analisis, Senal
from python.config import settings


class AgenteSenal(Agente):
    nombre = "senal"

    def __init__(self):
        self.previo = {}  # simbolo -> (ema_rapida - ema_lenta) anterior

    def procesar(self, a: Analisis) -> Optional[Senal]:
        diff = a.ema_rapida - a.ema_lenta
        anterior = self.previo.get(a.simbolo)
        self.previo[a.simbolo] = diff
        if anterior is None:
            return None
        if anterior <= 0 < diff and a.rsi < settings.RSI_MAX_COMPRA:
            return Senal(a.simbolo, "BUY", a.cierre, a.atr,
                         f"cruce alcista, RSI={a.rsi:.1f}")
        if anterior >= 0 > diff and a.rsi > settings.RSI_MIN_VENTA:
            return Senal(a.simbolo, "SELL", a.cierre, a.atr,
                         f"cruce bajista, RSI={a.rsi:.1f}")
        return None
