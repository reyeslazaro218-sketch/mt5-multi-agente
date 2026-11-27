"""Descarga de velas M1 históricas desde MetaTrader 5 (paquete MetaTrader5).

Requisitos: MT5 abierto con sesión DEMO iniciada y los símbolos en Market Watch.
"""
import logging
from datetime import datetime, timezone

from python.config import settings

log = logging.getLogger("backtest.datos")


class ErrorMT5(RuntimeError):
    pass


def _importar_mt5():
    try:
        import MetaTrader5 as mt5
    except ImportError as e:
        raise ErrorMT5("Falta el paquete: pip install MetaTrader5") from e
    return mt5


def conectar():
    """Inicializa MT5 y verifica que la cuenta sea demo (si MODO_DEMO)."""
    mt5 = _importar_mt5()
    if not mt5.initialize():
        raise ErrorMT5(f"No se pudo inicializar MT5: {mt5.last_error()}")
    info = mt5.account_info()
    if info is None:
        mt5.shutdown()
        raise ErrorMT5("No hay cuenta activa en MT5")
    # trade_mode 0 = DEMO en MetaTrader5
    if settings.MODO_DEMO and info.trade_mode != mt5.ACCOUNT_TRADE_MODE_DEMO:
        mt5.shutdown()
        raise ErrorMT5("MODO_DEMO=True pero la cuenta no es demo")
    log.info("Conectado a MT5 (cuenta %s)", info.login)
    return mt5


def descargar_m1(mt5, simbolo_broker: str, desde: datetime, hasta: datetime) -> list[dict]:
    """Devuelve velas M1 como lista de dicts ordenada por tiempo."""
    if not mt5.symbol_select(simbolo_broker, True):
        raise ErrorMT5(f"Símbolo no disponible en Market Watch: {simbolo_broker}")
    if desde.tzinfo is None:
        desde = desde.replace(tzinfo=timezone.utc)
    if hasta.tzinfo is None:
        hasta = hasta.replace(tzinfo=timezone.utc)
    velas = mt5.copy_rates_range(simbolo_broker, mt5.TIMEFRAME_M1, desde, hasta)
    if velas is None or len(velas) == 0:
        raise ErrorMT5(f"Sin datos para {simbolo_broker}: {mt5.last_error()}")
    return [
        {
            "tiempo": int(v["time"]),
            "apertura": float(v["open"]),
            "maximo": float(v["high"]),
            "minimo": float(v["low"]),
            "cierre": float(v["close"]),
            "volumen": int(v["tick_volume"]),
        }
        for v in velas
    ]


def descargar_todos(desde: datetime, hasta: datetime) -> dict[str, list[dict]]:
    """Descarga M1 para todos los símbolos de SIMBOLOS_BROKER. Cierra MT5 al terminar."""
    mt5 = conectar()
    try:
        return {
            logico: descargar_m1(mt5, real, desde, hasta)
            for logico, real in settings.SIMBOLOS_BROKER.items()
        }
    finally:
        mt5.shutdown()


def descargar_ticks(mt5, simbolo_broker: str, desde: datetime, hasta: datetime) -> list[dict]:
    """Obtiene los cambios de bid y ask para reconstruir precios ejecutables."""
    if desde.utcoffset() is None or hasta.utcoffset() is None or desde >= hasta:
        raise ValueError("Indique un intervalo válido con zona horaria")
    if not mt5.symbol_select(simbolo_broker, True):
        raise ErrorMT5(f"Símbolo no disponible: {simbolo_broker}")
    ticks = mt5.copy_ticks_range(simbolo_broker, desde, hasta, mt5.COPY_TICKS_INFO)
    if ticks is None or not len(ticks):
        raise ErrorMT5(f"Sin ticks para {simbolo_broker}: {mt5.last_error()}")
    return [
        {"ts": int(t["time_msc"]), "bid": float(t["bid"]), "ask": float(t["ask"])}
        for t in ticks if 0 < t["bid"] <= t["ask"]
    ]
