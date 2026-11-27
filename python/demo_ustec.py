"""Prueba demo de ruptura fallida de USTEC con ticks bid/ask."""
import argparse
import json
import logging
import math
import os
import time
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_DOWN
from pathlib import Path

from python.comunicacion.control_demo import ControlDemo
from python.comunicacion.cuenta_mt5 import CuentaMT5
from python.config import settings
from python.demo_ventas_h1 import demo_autorizada, permisos

SYMBOL = "USTEC"
MAGIC = 20261128
MINUTE = 60_000
DURATION = 60 * MINUTE
FEE_PER_LOT = 1.0
log = logging.getLogger("demo_ustec")


def clock(now):
    """ICMarkets mantiene su hora de servidor siete horas delante de Nueva York."""
    d = datetime.fromtimestamp(now, timezone.utc)
    march = d.replace(month=3, day=1, hour=7, minute=0, second=0, microsecond=0)
    start = march + timedelta(days=(6 - march.weekday()) % 7 + 7)
    november = d.replace(month=11, day=1, hour=6, minute=0, second=0, microsecond=0)
    end = november + timedelta(days=(6 - november.weekday()) % 7)
    broker = d + timedelta(hours=3 if start <= d < end else 2)
    opening = broker.replace(hour=16, minute=30, second=0, microsecond=0)
    return broker, int(opening.timestamp() * 1000)


def history(mt5, start, end):
    return mt5.copy_ticks_range(
        SYMBOL, datetime.fromtimestamp(start / 1000, timezone.utc),
        datetime.fromtimestamp(end / 1000, timezone.utc), mt5.COPY_TICKS_INFO,
    )


def opening_range(ticks, start, end):
    if ticks is None:
        return None
    ticks = [(int(q["time_msc"]), (float(q["bid"]) + float(q["ask"])) / 2)
             for q in ticks
             if start <= int(q["time_msc"]) < end and 0 < q["bid"] <= q["ask"]]
    if len(ticks) < 1000 or ticks[0][0] - start > 15_000 or end - ticks[-1][0] > 15_000:
        return None
    values = [p for _, p in ticks]
    low, high = min(values), max(values)
    return (low, high) if high > low else None


class FailedBreakout:
    def __init__(self, low, high, tick_size, fresh_open):
        self.low, self.high = low, high
        self.upper = high + 2 * tick_size
        self.lower = low - 2 * tick_size
        self.inside = fresh_open
        self.armed = {}

    def update(self, ts, mid):
        side = 1 if mid >= self.upper else -1 if mid <= self.lower else 0
        if side and self.inside:
            self.armed[side] = ts + MINUTE
        self.inside = side == 0
        for prior, expiry in list(self.armed.items()):
            if ts > expiry:
                self.armed.pop(prior)
            elif (prior == 1 and mid <= self.high) or (prior == -1 and mid >= self.low):
                self.armed.pop(prior)
                return -prior
        return None


def filling(mt5, info):
    if info.filling_mode & 2:
        return mt5.ORDER_FILLING_IOC
    if info.filling_mode & 1:
        return mt5.ORDER_FILLING_FOK
    return None


def make_order(mt5, equity, info, quote, side, width):
    step = info.trade_tick_size
    if not (step > 0 and info.trade_contract_size > 0 and info.volume_step > 0):
        return None, "especificaciones inválidas"
    risk = max(4, math.ceil(width / (2 * step))) * step
    spread = quote.ask - quote.bid
    if (spread + 2 * step + FEE_PER_LOT / info.trade_contract_size) / risk > 0.20:
        return None, "coste estimado superior a 0,20 R"
    price = quote.ask if side == 1 else quote.bid
    sl = round(round((price - side * risk) / step) * step, info.digits)
    tp_distance = math.ceil(1.5 * risk / step) * step
    tp = round(round((price + side * tp_distance) / step) * step, info.digits)
    position_price = quote.bid if side == 1 else quote.ask
    minimum = info.trade_stops_level * info.point
    if min(side * (position_price - sl), side * (tp - position_price)) <= minimum:
        return None, "stop u objetivo fuera de rango"
    order_type = mt5.ORDER_TYPE_BUY if side == 1 else mt5.ORDER_TYPE_SELL
    adverse = price + side * settings.DESVIACION_PUNTOS * info.point
    pnl = mt5.order_calc_profit(order_type, SYMBOL, 1.0, adverse, sl)
    if pnl is None or not math.isfinite(pnl) or pnl >= 0:
        return None, "pérdida al stop no verificable"
    budget = equity * settings.RIESGO_POR_OPERACION_PCT / 100
    loss = -pnl + FEE_PER_LOT
    volume_step = Decimal(str(info.volume_step))
    desired = Decimal(str(min(info.volume_max, budget / loss)))
    volume = float((desired / volume_step).to_integral_value(rounding=ROUND_DOWN) * volume_step)
    if volume < info.volume_min:
        return None, f"lote mínimo arriesga {info.volume_min * loss:.2f}, presupuesto {budget:.2f}"
    mode = filling(mt5, info)
    if mode is None:
        return None, "modo de llenado incompatible"
    return {
        "action": mt5.TRADE_ACTION_DEAL, "symbol": SYMBOL, "type": order_type,
        "volume": volume, "price": price, "sl": sl, "tp": tp, "magic": MAGIC,
        "deviation": settings.DESVIACION_PUNTOS, "type_filling": mode,
        "comment": "demo ustec ruptura",
    }, None


def reserve(path, payload):
    with path.open("x", encoding="utf-8") as file:
        json.dump(payload, file)
        file.flush()
        os.fsync(file.fileno())


def result_log(label, result):
    log.info("%s retcode=%s orden=%s deal=%s volumen=%s",
             label, getattr(result, "retcode", None), getattr(result, "order", None),
             getattr(result, "deal", None), getattr(result, "volume", None))


def uncertain(mt5, result):
    return result is None or result.retcode in (
        mt5.TRADE_RETCODE_TIMEOUT, mt5.TRADE_RETCODE_CONNECTION, mt5.TRADE_RETCODE_PLACED,
    )


def submit(mt5, login, state, reservation, order, reference, event_ts, control=None):
    control = control or ControlDemo(state)
    check = mt5.order_check(order)
    if check is None or check.retcode != 0:
        log.info("OrderCheck vetó la entrada: %s", getattr(check, "retcode", None))
        return
    account = mt5.account_info()
    if not demo_autorizada(mt5, account, login) or not permisos(account, mt5.terminal_info()):
        return
    positions, orders = mt5.positions_get(), mt5.orders_get()
    broker, open_at = clock(time.time())
    now = int(broker.timestamp() * 1000)
    age = now - event_ts
    latest = mt5.symbol_info_tick(SYMBOL)
    latest_price = (latest.ask if order["type"] == mt5.ORDER_TYPE_BUY else latest.bid) if latest else None
    if (positions != () or orders != () or not 0 <= age <= 2000
            or not open_at + 15 * MINUTE <= now < open_at + 90 * MINUTE
            or latest_price != order["price"] or account.equity < reference
            or not control.riesgo(account)):
        log.info("Veto: cambió la cotización, el patrimonio o la exposición antes de enviar")
        return
    reserve(reservation, {"sent_at": time.time(), "order": order})
    result = control.enviar(mt5, order)
    result_log("Entrada USTEC", result)
    if uncertain(mt5, result):
        reserve(state / "entrada_incierta.json", {"session": reservation.name})
        log.error("Resultado incierto: revisar MT5 antes de permitir nuevas entradas")


def exit_after_hour(mt5, login, state, position, broker):
    entries = sorted(state.glob("entrada-????-??-??.json"))
    if not entries:
        return
    entry = json.loads(entries[-1].read_text(encoding="utf-8"))
    if (time.time() - entry["sent_at"]) * 1000 < DURATION:
        return
    marker = state / f"cierre-{position.ticket}.json"
    if marker.exists():
        return
    account = mt5.account_info()
    if not demo_autorizada(mt5, account, login) or not permisos(account, mt5.terminal_info()):
        return
    current = mt5.positions_get(ticket=position.ticket)
    if not current or current[0].symbol != SYMBOL or current[0].magic != MAGIC:
        return
    position = current[0]
    info, quote = mt5.symbol_info(SYMBOL), mt5.symbol_info_tick(SYMBOL)
    if not info or not quote or not 0 < quote.bid <= quote.ask:
        return
    if not 0 <= int(broker.timestamp() * 1000) - quote.time_msc <= 3000:
        return
    buy = position.type == mt5.POSITION_TYPE_SELL
    mode = filling(mt5, info)
    if mode is None:
        return
    request = {
        "action": mt5.TRADE_ACTION_DEAL, "symbol": SYMBOL, "position": position.ticket,
        "type": mt5.ORDER_TYPE_BUY if buy else mt5.ORDER_TYPE_SELL,
        "price": quote.ask if buy else quote.bid, "volume": position.volume, "magic": MAGIC,
        "deviation": settings.DESVIACION_PUNTOS, "type_filling": mode, "comment": "demo time stop",
    }
    check = mt5.order_check(request)
    if check is None or check.retcode != 0:
        log.warning("OrderCheck vetó el cierre por tiempo: %s", getattr(check, "retcode", None))
        return
    account = mt5.account_info()
    if not demo_autorizada(mt5, account, login) or not permisos(account, mt5.terminal_info()):
        return
    reserve(marker, {"ticket": position.ticket, "sent_at": time.time()})
    result = mt5.order_send(request)
    result_log("Cierre por tiempo USTEC", result)
    if not uncertain(mt5, result):
        marker.unlink()


def quote_stream(mt5, cursor, consumed, now_ms):
    ticks = history(mt5, cursor, now_ms + 1000)
    rows = []
    if ticks is not None:
        for q in ticks:
            ts = int(q["time_msc"])
            if ts == cursor and consumed:
                consumed -= 1
                continue
            rows.append(q)
    return rows


def run(adapter, login, state, sending, control):
    mt5 = adapter.mt5
    info = mt5.symbol_info(SYMBOL)
    previous_session = None
    last_positions = None
    announced_wait = None
    detector = None
    cursor = consumed = 0
    range_requested = 0
    last_management = 0
    while not (state / "DETENER").exists():
        broker, opened_at = clock(time.time())
        now = int(broker.timestamp() * 1000)
        key = broker.date().isoformat()
        range_end = opened_at + 15 * MINUTE
        window_end = opened_at + 90 * MINUTE
        if key != previous_session:
            previous_session = key
            detector = None
            cursor = consumed = range_requested = 0
        if time.monotonic() - last_management >= 3:
            last_management = time.monotonic()
            snapshot = adapter.snapshot()
            if snapshot is None:
                account = mt5.account_info()
                if account and not demo_autorizada(mt5, account, login):
                    raise RuntimeError("Cambió la cuenta demo autorizada")
                time.sleep(3)
                continue
            account, positions, _ = snapshot
            if not demo_autorizada(mt5, account, login):
                raise RuntimeError("Cambió la cuenta demo autorizada")
            control.riesgo(account)
            positions = [p for p in positions if p.symbol == SYMBOL and p.magic == MAGIC]
            tickets = tuple(p.ticket for p in positions)
            if tickets != last_positions:
                log.info("Posiciones USTEC de la prueba: %s", tickets)
                last_positions = tickets
            if sending:
                for position in positions:
                    exit_after_hour(mt5, login, state, position, broker)
        daily = state / f"entrada-{key}.json"
        paused = (state / "entrada_incierta.json").exists()
        if broker.weekday() >= 5 or not range_end <= now < window_end or daily.exists() or paused:
            phase = "bloqueo por orden incierta" if paused else "entrada ya enviada" if daily.exists() else "fuera de ventana de entradas"
            if announced_wait != (key, phase):
                log.info("USTEC %s (%s); ventana 09:45–11:00 Nueva York", phase, key)
                announced_wait = (key, phase)
            time.sleep(1)
            continue
        if detector is None:
            if now - range_requested < 5000:
                time.sleep(.25)
                continue
            range_requested = now
            bounds = opening_range(history(mt5, opened_at, range_end), opened_at, range_end)
            if bounds is None:
                log.warning("Rango de apertura sin cobertura suficiente")
                continue
            low, high = bounds
            detector = FailedBreakout(low, high, info.trade_tick_size, now - range_end <= 2000)
            cursor = max(range_end, now - 1000)
            log.info("Rango USTEC validado: %.2f–%.2f (%s)", low, high, key)
        rows = quote_stream(mt5, cursor, consumed, now)
        now = int(clock(time.time())[0].timestamp() * 1000)
        for q in rows:
            ts = int(q["time_msc"])
            if ts < cursor:
                continue
            if ts != cursor:
                cursor, consumed = ts, 0
            consumed += 1
            if not (range_end <= ts < window_end and 0 < q["bid"] <= q["ask"]):
                continue
            side = detector.update(ts, (float(q["bid"]) + float(q["ask"])) / 2)
            if side is None or not 0 <= now - ts <= 2000:
                continue
            log.info("Señal de ruptura fallida USTEC: %s ts=%s", "BUY" if side == 1 else "SELL", ts)
            if not sending:
                continue
            with control.entrada() as disponible:
                if not disponible:
                    log.info("Entrada vetada: otro envío en curso o pendiente de verificar")
                    continue
                snapshot = adapter.snapshot()
                if snapshot is None:
                    continue
                account, positions, orders = snapshot
                if (not demo_autorizada(mt5, account, login) or positions or orders
                        or not permisos(account, mt5.terminal_info())
                        or not control.riesgo(account) or daily.exists() or paused):
                    log.info("Entrada vetada por cuenta, exposición o riesgo")
                    continue
                quote = mt5.symbol_info_tick(SYMBOL)
                quote_time = int(clock(time.time())[0].timestamp() * 1000)
                if not quote or not 0 < quote.bid <= quote.ask or not 0 <= quote_time - quote.time_msc <= 2000:
                    continue
                order, reason = make_order(mt5, account.equity, info, quote, side, high-low)
                if order is None:
                    log.info("Entrada vetada: %s", reason)
                    continue
                submit(mt5, login, state, daily, order, account.equity, ts, control)
            if daily.exists():
                break
        time.sleep(.25)


def main():
    import msvcrt

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--login", type=int, required=True)
    parser.add_argument("--estado", type=Path, required=True)
    parser.add_argument("--compartido", type=Path)
    parser.add_argument("--enviar", action="store_true")
    args = parser.parse_args()
    args.estado.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    with (args.estado / "ejecucion.lock").open("a+b") as lock:
        lock.seek(0)
        msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        adapter = CuentaMT5()
        try:
            snapshot = adapter.snapshot()
            mt5 = adapter.mt5
            if not settings.MODO_DEMO or not snapshot or not demo_autorizada(mt5, snapshot[0], args.login):
                raise RuntimeError("Cuenta demo no verificada")
            if args.enviar and not permisos(snapshot[0], mt5.terminal_info()):
                raise RuntimeError("Permisos de trading demo no verificados")
            if not mt5.symbol_select(SYMBOL, True):
                raise RuntimeError("USTEC no disponible")
            info, quote = mt5.symbol_info(SYMBOL), mt5.symbol_info_tick(SYMBOL)
            broker, _ = clock(time.time())
            if info is None or (quote and abs(int(broker.timestamp()*1000) - quote.time_msc) > 15_000
                                and abs(time.time()*1000 - quote.time_msc) < 15_000):
                raise RuntimeError("Las marcas de tiempo del bróker no coinciden con la sesión configurada")
            log.info("Prueba ruptura fallida USTEC iniciada enviar=%s lote_min=%.2f", args.enviar, info.volume_min)
            run(adapter, args.login, args.estado, args.enviar, ControlDemo(args.estado, args.compartido))
        finally:
            if adapter.mt5 is not None:
                adapter.mt5.shutdown()


if __name__ == "__main__":
    main()
