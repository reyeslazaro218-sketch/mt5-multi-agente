"""Agente de análisis: acumula velas M1 por símbolo y calcula indicadores."""
from collections import deque
from typing import Optional

from python.agentes.base import Agente, Analisis
from python.config import settings


def ema(valores, periodo):
    """EMA simple sobre una lista; devuelve el último valor."""
    k = 2.0 / (periodo + 1)
    e = valores[0]
    for v in valores[1:]:
        e = v * k + e * (1 - k)
    return e


def rsi(cierres, periodo):
    """RSI de Wilder; devuelve el último valor."""
    ganancias, perdidas = 0.0, 0.0
    for i in range(1, periodo + 1):
        d = cierres[i] - cierres[i - 1]
        ganancias += max(d, 0)
        perdidas += max(-d, 0)
    media_g, media_p = ganancias / periodo, perdidas / periodo
    for i in range(periodo + 1, len(cierres)):
        d = cierres[i] - cierres[i - 1]
        media_g = (media_g * (periodo - 1) + max(d, 0)) / periodo
        media_p = (media_p * (periodo - 1) + max(-d, 0)) / periodo
    if media_p == 0:
        return 100.0
    rs = media_g / media_p
    return 100.0 - 100.0 / (1.0 + rs)


def atr(velas, periodo):
    """ATR simple (media de rangos verdaderos de las últimas `periodo` velas)."""
    rangos = []
    for i in range(1, len(velas)):
        v, previa = velas[i], velas[i - 1]
        rangos.append(max(v["maximo"] - v["minimo"],
                          abs(v["maximo"] - previa["cierre"]),
                          abs(v["minimo"] - previa["cierre"])))
    ultimos = rangos[-periodo:]
    return sum(ultimos) / len(ultimos)


class AgenteAnalisis(Agente):
    nombre = "analisis"

    def __init__(self):
        self.velas = {}
        self.minimo_velas = max(settings.EMA_LENTA, settings.RSI_PERIODO + 1,
                                settings.ATR_PERIODO + 1) + 5

    def procesar(self, vela: dict) -> Optional[Analisis]:
        """Recibe un mensaje `vela`; devuelve Analisis cuando hay datos suficientes."""
        simbolo = vela["simbolo"]
        buf = self.velas.setdefault(simbolo, deque(maxlen=500))
        buf.append(vela)
        if len(buf) < self.minimo_velas:
            return None
        lista = list(buf)
        cierres = [v["cierre"] for v in lista]
        return Analisis(
            simbolo=simbolo,
            cierre=cierres[-1],
            ema_rapida=ema(cierres[-settings.EMA_RAPIDA * 4:], settings.EMA_RAPIDA),
            ema_lenta=ema(cierres[-settings.EMA_LENTA * 4:], settings.EMA_LENTA),
            rsi=rsi(cierres[-(settings.RSI_PERIODO * 4):], settings.RSI_PERIODO),
            atr=atr(lista, settings.ATR_PERIODO),
        )
