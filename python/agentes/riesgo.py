"""Agente de riesgo: puede vetar señales y calcula lote, SL y TP.

El lote se calcula para arriesgar RIESGO_POR_OPERACION_PCT del balance si
se toca el SL (distancia = ATR * SL_ATR_MULT). Requiere conocer el valor
por punto del símbolo, que se configura en settings.VALOR_POR_UNIDAD.
"""
import logging
from typing import Optional

from python.agentes.base import Agente, OrdenAprobada, Senal
from python.config import settings

log = logging.getLogger("riesgo")


class AgenteRiesgo(Agente):
    nombre = "riesgo"

    def __init__(self, balance_inicial: float = settings.BALANCE_INICIAL):
        self.balance_inicial_dia = balance_inicial
        self.balance = balance_inicial
        self.posiciones = set()  # símbolos con posición abierta

    def actualizar_balance(self, balance: float) -> None:
        self.balance = balance

    def reiniciar_dia(self) -> None:
        self.balance_inicial_dia = self.balance

    def perdida_diaria_pct(self) -> float:
        return max(0.0, (self.balance_inicial_dia - self.balance)
                   / self.balance_inicial_dia * 100.0)

    def registrar_apertura(self, simbolo: str) -> None:
        self.posiciones.add(simbolo)

    def registrar_cierre(self, simbolo: str) -> None:
        self.posiciones.discard(simbolo)

    def procesar(self, s: Senal) -> Optional[OrdenAprobada]:
        if self.perdida_diaria_pct() >= settings.PERDIDA_MAXIMA_DIARIA_PCT:
            log.warning("Veto %s: límite de pérdida diaria alcanzado", s.simbolo)
            return None
        if s.simbolo in self.posiciones:
            log.info("Veto %s: ya hay posición abierta", s.simbolo)
            return None
        if len(self.posiciones) >= settings.MAX_POSICIONES_ABIERTAS:
            log.info("Veto %s: máximo de posiciones abiertas", s.simbolo)
            return None
        if s.atr <= 0:
            return None

        dist_sl = s.atr * settings.SL_ATR_MULT
        dist_tp = s.atr * settings.TP_ATR_MULT
        valor = settings.VALOR_POR_UNIDAD.get(s.simbolo, 1.0)
        riesgo_dinero = self.balance * settings.RIESGO_POR_OPERACION_PCT / 100.0
        lote = riesgo_dinero / (dist_sl * valor)
        lote = max(settings.LOTE_MINIMO,
                   min(settings.LOTE_MAXIMO,
                       round(lote / settings.LOTE_PASO) * settings.LOTE_PASO))

        if s.lado == "BUY":
            sl, tp = s.precio - dist_sl, s.precio + dist_tp
        else:
            sl, tp = s.precio + dist_sl, s.precio - dist_tp
        return OrdenAprobada(s.simbolo, s.lado, round(lote, 2),
                             round(sl, 5), round(tp, 5))
