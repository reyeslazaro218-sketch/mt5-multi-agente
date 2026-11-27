"""Prueba continua de XAUUSD M5 con ventas filtradas por EMA 50 en H1."""
import argparse
import json
import logging
import math
import os
import time
from pathlib import Path

from python.agentes.analisis import AgenteAnalisis, ema
from python.agentes.riesgo import riesgo_disponible
from python.agentes.senal import AgenteSenal
from python.comunicacion.cuenta_mt5 import CuentaMT5
from python.config import settings

SYMBOL = "XAUUSD"
SERVER = "ICMarketsSC-Demo"
MAGIC = 20261127
log = logging.getLogger("demo_ventas_h1")


def detectar_cruce(velas):
    analisis = AgenteAnalisis()
    senal = AgenteSenal()
    anterior = None
    resultado = None
    for vela in velas:
        ts = int(vela["time"]) * 1000
        if anterior is not None and ts - anterior != settings.VELA_MS:
            senal.previo.clear()
        anterior = ts
        dato = analisis.procesar({
            "simbolo": SYMBOL, "ts": ts, "cierre": float(vela["close"]),
            "maximo": float(vela["high"]), "minimo": float(vela["low"]),
        })
        resultado = senal.procesar(dato) if dato is not None else None
    return resultado


def confirmar_venta(senal, h1, cierre_m5):
    if senal is None or senal.lado != "SELL" or h1 is None:
        return False
    cerradas = [b for b in h1 if int(b["time"]) + 3600 <= cierre_m5]
    if len(cerradas) < 50 or cierre_m5 - (int(cerradas[-1]["time"]) + 3600) >= 3600:
        return False
    precios = [float(b["close"]) for b in cerradas]
    return precios[-1] < ema(precios, 50)


def entrada(mt5, cuenta, orden, login, vela, pendiente, offset_broker):
    tick = mt5.symbol_info_tick(SYMBOL)
    info = mt5.symbol_info(SYMBOL)
    if tick is None or info is None or abs(time.time() + offset_broker - tick.time) > 15:
        log.info("Veto: cotización de ejecución no disponible")
        return
    if not (0 < tick.bid <= tick.ask and orden.tp < tick.ask < orden.sl):
        log.info("Veto: stop/objetivo fuera de rango")
        return
    perdida = mt5.order_calc_profit(
        mt5.ORDER_TYPE_SELL, SYMBOL, orden.lote,
        tick.bid - settings.DESVIACION_PUNTOS * info.point, orden.sl,
    )
    if perdida is None or not math.isfinite(perdida) or not (
        0 < -perdida <= cuenta.equity * settings.RIESGO_POR_OPERACION_PCT / 100
    ):
        log.info("Veto: tamaño fuera del presupuesto")
        return
    if info.filling_mode & 2:
        filling = mt5.ORDER_FILLING_IOC
    elif info.filling_mode & 1:
        filling = mt5.ORDER_FILLING_FOK
    else:
        log.info("Veto: modo de ejecución no compatible")
        return
    solicitud = {
        "action": mt5.TRADE_ACTION_DEAL, "symbol": SYMBOL,
        "type": mt5.ORDER_TYPE_SELL, "volume": orden.lote, "price": tick.bid,
        "sl": orden.sl, "tp": orden.tp, "magic": MAGIC,
        "deviation": settings.DESVIACION_PUNTOS, "type_filling": filling,
        "comment": "demo ventas h1",
    }
    chequeo = mt5.order_check(solicitud)
    if chequeo is None or chequeo.retcode != 0:
        log.warning("OrderCheck rechazado: %s", getattr(chequeo, "retcode", mt5.last_error()))
        return
    actual = mt5.account_info()
    terminal = mt5.terminal_info()
    if not demo_autorizada(mt5, actual, login) or not permisos(actual, terminal):
        log.warning("Veto: cambió la cuenta o el permiso de ejecución")
        return
    posiciones, ordenes = mt5.positions_get(), mt5.orders_get()
    if (posiciones is None or ordenes is None
            or len(posiciones) + len(ordenes) >= settings.MAX_POSICIONES_ABIERTAS
            or any(p.symbol == SYMBOL for p in (*posiciones, *ordenes))
            or not 0 < -perdida <= actual.equity * settings.RIESGO_POR_OPERACION_PCT / 100):
        log.info("Veto: cambió la exposición o el patrimonio")
        return
    with pendiente.open("x", encoding="utf-8") as archivo:
        json.dump({"vela": vela, "login": login, "solicitud": solicitud}, archivo)
        archivo.flush()
        os.fsync(archivo.fileno())
    resultado = mt5.order_send(solicitud)
    if resultado is None or resultado.retcode in (
        mt5.TRADE_RETCODE_TIMEOUT, mt5.TRADE_RETCODE_CONNECTION,
    ):
        log.error("Resultado incierto. Nuevas entradas bloqueadas: %s", resultado)
        return
    log.info("Resultado MT5 retcode=%s orden=%s deal=%s volumen=%s",
             resultado.retcode, resultado.order, resultado.deal, resultado.volume)
    pendiente.unlink()


def demo_autorizada(mt5, cuenta, login):
    return (cuenta is not None and cuenta.trade_mode == mt5.ACCOUNT_TRADE_MODE_DEMO
            and cuenta.server == SERVER and cuenta.login == login)


def permisos(cuenta, terminal):
    return (terminal is not None and terminal.connected and terminal.trade_allowed
            and not terminal.tradeapi_disabled and cuenta.trade_allowed and cuenta.trade_expert)


def ejecutar(adapter, login, estado, enviar):
    pendiente = estado / "orden_pendiente.json"
    ultima_vela = None
    ultima_posicion = None
    while not (estado / "DETENER").exists():
        lectura = adapter.snapshot()
        mt5 = adapter.mt5
        if lectura is None:
            actual = mt5.account_info()
            if actual is not None and not demo_autorizada(mt5, actual, login):
                raise RuntimeError("Cambió la cuenta demo autorizada")
            log.warning("Sin lectura de MT5. Entradas en pausa")
            time.sleep(30)
            continue
        if not demo_autorizada(mt5, lectura[0], login):
            raise RuntimeError("Cambió la cuenta demo autorizada")
        cuenta, posiciones, ordenes = lectura
        permitida = riesgo_disponible(cuenta, estado)
        propios = tuple(p.ticket for p in posiciones if p.magic == MAGIC)
        if propios != ultima_posicion:
            log.info("Posiciones de la prueba: %s", propios)
            ultima_posicion = propios
        velas = mt5.copy_rates_from_pos(SYMBOL, mt5.TIMEFRAME_M5, 1, 100)
        if velas is not None and len(velas):
            ts = int(velas[-1]["time"])
            if ts != ultima_vela:
                primera = ultima_vela is None
                ultima_vela = ts
                cierre = ts + settings.VELA_MS // 1000
                log.info("Vela M5 cerrada ts=%s riesgo_habilitado=%s", ts, permitida)
                if not primera and 0 <= time.time() + adapter.offset_broker - cierre <= 30:
                    cruce = detectar_cruce(velas)
                    if cruce is not None and cruce.lado == "SELL":
                        h1 = mt5.copy_rates_from_pos(SYMBOL, mt5.TIMEFRAME_H1, 1, 250)
                        if confirmar_venta(cruce, h1, cierre):
                            log.info("Señal SELL confirmada por EMA50 H1: %s", cruce.motivo)
                            if (enviar and permitida and not pendiente.exists()
                                    and len(posiciones) + len(ordenes) < settings.MAX_POSICIONES_ABIERTAS
                                    and not any(p.symbol == SYMBOL for p in (*posiciones, *ordenes))
                                    and permisos(cuenta, mt5.terminal_info())):
                                plan = adapter.preparar(cruce, cuenta.equity)
                                if plan is not None:
                                    entrada(mt5, cuenta, plan, login, ts, pendiente, adapter.offset_broker)
                                else:
                                    log.info("Veto: sin lote válido dentro del presupuesto")
                            else:
                                log.info("Entrada omitida por estado de cuenta, permisos o riesgo")
                        else:
                            log.info("Cruce SELL descartado por filtro H1")
        time.sleep(3)


def main():
    import msvcrt

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--login", type=int, required=True)
    parser.add_argument("--estado", type=Path, required=True)
    parser.add_argument("--offset-broker", type=int, required=True, help="Segundos del servidor respecto a UTC")
    parser.add_argument("--enviar", action="store_true")
    args = parser.parse_args()
    args.estado.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    with (args.estado / "ejecucion.lock").open("a+b") as lock:
        lock.seek(0)
        msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        adapter = CuentaMT5(offset_broker=args.offset_broker)
        try:
            lectura = adapter.snapshot()
            mt5 = adapter.mt5
            if not settings.MODO_DEMO or lectura is None or not demo_autorizada(mt5, lectura[0], args.login):
                raise RuntimeError("Arranque bloqueado: cuenta demo sin confirmar")
            if args.enviar and not permisos(lectura[0], mt5.terminal_info()):
                raise RuntimeError("Arranque bloqueado: MT5 no permite trading algorítmico")
            if not mt5.symbol_select(SYMBOL, True):
                raise RuntimeError("XAUUSD no disponible")
            log.info("Prueba XAUUSD M5 ventas H1 iniciada en %s enviar=%s", SERVER, args.enviar)
            ejecutar(adapter, args.login, args.estado, args.enviar)
        finally:
            if adapter.mt5 is not None:
                adapter.mt5.shutdown()


if __name__ == "__main__":
    main()
