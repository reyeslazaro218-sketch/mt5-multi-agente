"""Lecturas de la cuenta demo y preparación de órdenes con datos del bróker."""
import math
import os
import time
from decimal import Decimal, ROUND_DOWN

from python.agentes.base import OrdenAprobada
from python.config import settings


class CuentaMT5:
    def __init__(self):
        self.mt5 = None
        self.identidad = None

    def snapshot(self):
        if self.mt5 is None:
            import MetaTrader5
            self.mt5 = MetaTrader5
        mt5 = self.mt5
        if not mt5.initialize(os.environ["MT5_PATH"]):
            return None
        cuenta = mt5.account_info()
        terminal = mt5.terminal_info()
        if (cuenta is None or terminal is None or not terminal.connected
                or cuenta.trade_mode != mt5.ACCOUNT_TRADE_MODE_DEMO):
            return None
        identidad = (cuenta.login, cuenta.server)
        if self.identidad is None:
            self.identidad = identidad
        if identidad != self.identidad:
            return None
        posiciones = mt5.positions_get()
        pendientes = mt5.orders_get()
        if posiciones is None or pendientes is None:
            return None
        return cuenta, posiciones, pendientes

    def preparar(self, senal, equity):
        mt5 = self.mt5
        s = senal.simbolo
        info, tick = mt5.symbol_info(s), mt5.symbol_info_tick(s)
        if (info is None or tick is None or not (0 < tick.bid <= tick.ask)
                or abs(time.time() - tick.time) > 15 or not math.isfinite(senal.atr) or senal.atr <= 0):
            return None
        if not (info.trade_tick_size > 0 and info.volume_step > 0):
            return None
        compra = senal.lado == "BUY"
        signo = 1 if compra else -1
        precio = tick.ask if compra else tick.bid
        referencia = tick.bid if compra else tick.ask
        tipo = mt5.ORDER_TYPE_BUY if compra else mt5.ORDER_TYPE_SELL
        minimo = info.trade_stops_level * info.point

        def nivel(distancia):
            paso = info.trade_tick_size
            return round(round((precio + signo * distancia) / paso) * paso, info.digits)

        sl = nivel(-senal.atr * settings.SL_ATR_MULT)
        tp = nivel(senal.atr * settings.TP_ATR_MULT)
        if min(signo * (referencia - sl), signo * (tp - referencia)) <= minimo:
            return None
        adverso = precio + signo * settings.DESVIACION_PUNTOS * info.point
        perdida = mt5.order_calc_profit(tipo, s, 1.0, adverso, sl)
        if perdida is None or not math.isfinite(perdida) or perdida >= 0:
            return None
        paso = Decimal(str(info.volume_step))
        ideal = min(info.volume_max, equity * settings.RIESGO_POR_OPERACION_PCT / 100 / -perdida)
        lote = float((Decimal(str(ideal)) / paso).to_integral_value(rounding=ROUND_DOWN) * paso)
        if lote < info.volume_min:
            return None
        margen = mt5.order_calc_margin(tipo, s, lote, precio)
        cuenta = mt5.account_info()
        if margen is None or cuenta is None or not 0 <= margen <= cuenta.margin_free:
            return None
        return OrdenAprobada(s, senal.lado, lote, sl, tp)
