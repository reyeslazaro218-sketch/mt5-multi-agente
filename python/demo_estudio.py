"""Perfiles experimentales. Coordina sus entradas con el proceso USTEC."""
import argparse
import json
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np

from python.agentes.analisis import AgenteAnalisis
from python.agentes.senal import AgenteSenal
from python.comunicacion.control_demo import ControlDemo, bloqueo
from python.comunicacion.cuenta_mt5 import CuentaMT5
from python.config import settings
from python.demo_ustec import FailedBreakout, clock, filling, make_order, opening_range, reserve, result_log, uncertain
from python.demo_ventas_h1 import demo_autorizada, permisos

log = logging.getLogger("demo_estudio")
MIN = 60_000


@dataclass(frozen=True)
class Profile:
    symbol: str
    magic: int
    timeframe: str
    hold: int
    target: float
    fees: float
    sending: bool = True


PROFILES = (
    Profile("XAUUSD", 20261129, "M5", 45, 1.5, 7),
    Profile("EURUSD", 20261130, "M15", 90, 2, 7),
    Profile("GBPUSD", 20261201, "ticks", 60, 1.5, 7),
    Profile("BTCUSD", 20261202, "M1", 45, 5/3, 0, False),
)


def london_hour(broker, now):
    # El servidor alterna UTC+2/+3 con EE. UU. y Londres cambia en otras fechas.
    offset = round((broker.timestamp() - now) / 3600)
    spring = broker.replace(month=3, day=31).date()
    fall = broker.replace(month=10, day=31).date()
    spring -= timedelta(days=(spring.weekday()+1) % 7)
    fall -= timedelta(days=(fall.weekday()+1) % 7)
    return 8 - int(spring <= broker.date() < fall) + offset


def milliseconds(dt):
    return int(dt.timestamp() * 1000)


def ticks(mt5, symbol, start, end):
    return mt5.copy_ticks_range(
        symbol, datetime.fromtimestamp(start/1000, timezone.utc),
        datetime.fromtimestamp(end/1000, timezone.utc), mt5.COPY_TICKS_INFO,
    )


def average(values, length):
    result = np.empty(len(values))
    result[0] = values[0]
    for i in range(1, len(values)):
        result[i] = result[i-1] + (values[i]-result[i-1])*2/(length+1)
    return result


def period_atr(bars):
    prev = bars["close"][-15:-1]
    hi = bars["high"][-14:]
    lo = bars["low"][-14:]
    return float(np.mean(np.maximum.reduce((hi-lo, abs(hi-prev), abs(lo-prev)))))


def ema_pullback(mt5, profile, bars, close_ts):
    c = bars["close"]
    fast = average(c, 20)
    if profile.symbol == "XAUUSD":
        slow = average(c, 100)
        side = 1 if fast[-1]>slow[-1] else -1 if fast[-1]<slow[-1] else 0
        distance = .8 * period_atr(bars)
    else:
        trend = mt5.copy_rates_from_pos(profile.symbol, mt5.TIMEFRAME_H1, 1, 250)
        if trend is None:
            return None
        trend = trend[trend["time"]+3600<=close_ts//1000]
        if len(trend)<100 or close_ts//1000-int(trend[-1]["time"])-3600>=3600:
            return None
        slow = average(trend["close"], 50)
        last = trend[-1]["close"]
        side = 1 if last>slow[-1] else -1 if last<slow[-1] else 0
        if side*(fast[-1]-fast[-5])<=0:
            return None
        distance = 1.5 * period_atr(bars)
    if side*(c[-2]-fast[-2])<=0 and side*(c[-1]-fast[-1])>0:
        return side,distance
    return None


def btc_cross(bars):
    gaps = np.where(np.diff(bars["time"])!=60)[0]
    if len(gaps):
        bars = bars[gaps[-1]+1:]
    analysis, signal = AgenteAnalisis(), AgenteSenal()
    decision = None
    for bar in bars:
        data = analysis.procesar(dict(simbolo="BTCUSD",cierre=float(bar["close"]),
                                       maximo=float(bar["high"]),minimo=float(bar["low"])))
        decision = signal.procesar(data) if data is not None else None
    if decision:
        return (1 if decision.lado=="BUY" else -1),1.5*decision.atr
    return None


def gold_spread_limit(mt5, ts):
    bars = mt5.copy_rates_from_pos("XAUUSD", mt5.TIMEFRAME_M1, 1, 20)
    if bars is None:
        return None
    bars = bars[bars["time"]+60<=ts//1000]
    if len(bars)<15 or int(bars[-1]["time"])+60!=ts//1000 or bars[-1]["time"]-bars[-15]["time"]!=14*60:
        return None
    history = ticks(mt5,"XAUUSD",ts-60*MIN-3000,ts)
    if history is None or not len(history):
        return None
    history = history[(history["bid"]>0)&(history["ask"]>=history["bid"])]
    grid = np.arange(ts-60*MIN,ts,MIN)
    indexes = np.searchsorted(history["time_msc"],grid,side="right")-1
    known = indexes>=0
    if not np.any(known):
        return None
    quote = history[indexes[known]]
    fresh = grid[known]-quote["time_msc"]<=3000
    spreads = (quote["ask"]-quote["bid"])[fresh]
    if len(spreads)<30:
        return None
    return min(float(np.quantile(spreads,.75)),.20*period_atr(bars))


class LondonFade:
    def __init__(self):
        self.day = None

    def poll(self, mt5, day, now, opening):
        if day!=self.day:
            self.day = day
            self.detector = None
            self.retry = 0
            self.cursor = self.consumed = 0
        end_range = opening+30*MIN
        if not end_range<=now<opening+120*MIN:
            return None
        if self.detector is None:
            if now<self.retry:
                return None
            self.retry = now+5000
            limits = opening_range(ticks(mt5,"GBPUSD",opening,end_range),opening,end_range,minimum=300)
            info = mt5.symbol_info("GBPUSD")
            if not limits or not info:
                return None
            lo,hi = limits
            self.detector = FailedBreakout(lo,hi,info.trade_tick_size,now-end_range<=2000,
                                           buffer=.0001,return_ms=120000)
            self.distance = (hi-lo)/2
            self.cursor = max(end_range,now-500)
            log.info("GBPUSD rango de Londres %.5f–%.5f",lo,hi)
        raw = ticks(mt5,"GBPUSD",self.cursor,now+1000)
        if raw is None:
            return None
        used = self.consumed
        decision = None
        for q in raw:
            ts = int(q["time_msc"])
            if ts<self.cursor:
                continue
            if ts==self.cursor and used>0:
                used-=1
                continue
            if ts!=self.cursor:
                self.cursor,self.consumed=ts,0
            self.consumed+=1
            if not 0<q["bid"]<=q["ask"] or not end_range<=ts<opening+120*MIN:
                continue
            side = self.detector.update(ts,float((q["bid"]+q["ask"])/2))
            if side and 0<=now-ts<=2000 and decision is None:
                decision = ts,side,self.distance
        return decision


def attempt(mt5, profile, login, control, state, day, decision, sending):
    ts,side,distance = decision
    if not np.isfinite(distance) or distance<=0:
        return
    log.info("%s señal %s stop=%.5f",profile.symbol,"BUY" if side==1 else "SELL",distance)
    if not (sending and profile.sending):
        return
    with control.entrada() as available:
        account, terminal = mt5.account_info(), mt5.terminal_info()
        p,o = mt5.positions_get(),mt5.orders_get()
        if (not available or not demo_autorizada(mt5,account,login) or not permisos(account,terminal)
                or p!=() or o!=() or not control.riesgo(account)):
            log.info("%s veto riesgo, exposición o envío pendiente",profile.symbol)
            return
        info,q = mt5.symbol_info(profile.symbol),mt5.symbol_info_tick(profile.symbol)
        now = milliseconds(clock(time.time())[0])
        timeout = 2000 if profile.timeframe=="ticks" else 10000
        if not info or not q or not 0<q.bid<=q.ask or not 0<=now-q.time_msc<=3000 or not 0<=now-ts<=timeout:
            log.info("%s veto cotización fuera de plazo",profile.symbol)
            return
        if profile.symbol=="XAUUSD":
            ceiling = gold_spread_limit(mt5,ts)
            if ceiling is None or q.ask-q.bid>ceiling:
                log.info("XAUUSD veto spread de sesión")
                return
        order,why = make_order(mt5, account.equity,info,q,side,2*distance,
                              symbol=profile.symbol,magic=profile.magic,
                              fee_per_lot=profile.fees,target_r=profile.target)
        if order is None:
            log.info("%s veto: %s",profile.symbol,why)
            return
        check = mt5.order_check(order)
        actual,terminal = mt5.account_info(),mt5.terminal_info()
        now = milliseconds(clock(time.time())[0])
        if (check is None or check.retcode!=0 or not demo_autorizada(mt5,actual,login)
                or not permisos(actual,terminal) or actual.equity<account.equity
                or mt5.positions_get()!=() or mt5.orders_get()!=() or not 0<=now-ts<=timeout):
            log.info("%s veto OrderCheck o estado cambiado retcode=%s",
                     profile.symbol,getattr(check,"retcode",None))
            return
        journal = state / f"{profile.symbol}-{day}.json"
        if journal.exists():
            return
        reserve(journal,{"sent_at":time.time(),"order":order})
        result_log(f"Entrada {profile.symbol}",control.enviar(mt5,order))


def close_due(mt5, profile, position, state, login):
    entries = sorted(state.glob(f"{profile.symbol}-????-??-??.json"))
    if not entries:
        return
    last = json.loads(entries[-1].read_text(encoding="utf-8"))
    if time.time()-last["sent_at"]<profile.hold*60:
        return
    checkfile = state / f"cierre-{position.ticket}.json"
    if checkfile.exists():
        return
    account = mt5.account_info()
    if not demo_autorizada(mt5,account,login) or not permisos(account,mt5.terminal_info()):
        return
    row = mt5.positions_get(ticket=position.ticket)
    if not row or row[0].symbol!=profile.symbol or row[0].magic!=profile.magic:
        return
    position = row[0]
    quote,info = mt5.symbol_info_tick(profile.symbol),mt5.symbol_info(profile.symbol)
    if not info or not quote or not 0<quote.bid<=quote.ask:
        return
    mode = filling(mt5,info)
    if mode is None or not 0<=milliseconds(clock(time.time())[0])-quote.time_msc<=3000:
        return
    buy = position.type==mt5.POSITION_TYPE_SELL
    order = dict(action=mt5.TRADE_ACTION_DEAL,symbol=profile.symbol,position=position.ticket,
                 volume=position.volume,type=mt5.ORDER_TYPE_BUY if buy else mt5.ORDER_TYPE_SELL,
                 price=quote.ask if buy else quote.bid,magic=profile.magic,
                 deviation=settings.DESVIACION_PUNTOS,type_filling=mode,comment="demo time stop")
    verify = mt5.order_check(order)
    a,t = mt5.account_info(),mt5.terminal_info()
    if verify is None or verify.retcode!=0 or not demo_autorizada(mt5,a,login) or not permisos(a,t):
        return
    reserve(checkfile,{"ticket":position.ticket})
    result = mt5.order_send(order)
    result_log(f"Cierre por tiempo {profile.symbol}",result)
    if not uncertain(mt5,result):
        checkfile.unlink()


def run(mt5, adapter, login, state, control, sending):
    lastbars = {}
    session_log = {}
    fade = LondonFade()
    management = 0
    frames = {"M1":mt5.TIMEFRAME_M1,"M5":mt5.TIMEFRAME_M5,"M15":mt5.TIMEFRAME_M15}
    lengths = {"M1":60,"M5":300,"M15":900}
    while not (state/"DETENER").exists():
        epoch = time.time()
        broker, _ = clock(epoch)
        now = milliseconds(broker)
        day = broker.date().isoformat()
        lh = broker.replace(hour=london_hour(broker, epoch),minute=0,second=0,microsecond=0)
        ny = broker.replace(hour=15,minute=0,second=0,microsecond=0)
        if time.monotonic()-management>=3:
            management = time.monotonic()
            snap = adapter.snapshot()
            if not snap:
                a = mt5.account_info()
                if a and not demo_autorizada(mt5,a,login):
                    raise RuntimeError("La cuenta dejó de ser la demo autorizada")
                time.sleep(3)
                continue
            a,p,_ = snap
            if not demo_autorizada(mt5,a,login):
                raise RuntimeError("La cuenta dejó de ser la demo autorizada")
            control.riesgo(a)
            if sending:
                for pos in p:
                    for profile in PROFILES:
                        if (pos.symbol,pos.magic)==(profile.symbol,profile.magic):
                            close_due(mt5,profile,pos,state,login)
            for profile in PROFILES:
                if profile.timeframe=="ticks":
                    continue
                start = ny if profile.symbol=="XAUUSD" else lh
                active = profile.symbol=="BTCUSD" or (broker.weekday()<5 and start<=broker<start+timedelta(hours=4))
                if session_log.get(profile.symbol)!=(day,active):
                    log.info("%s ventana activa=%s",profile.symbol,active)
                    session_log[profile.symbol]=(day,active)
                if not active or (state/f"{profile.symbol}-{day}.json").exists():
                    continue
                recent = mt5.copy_rates_from_pos(profile.symbol,frames[profile.timeframe],1,2)
                if recent is None or len(recent)<2:
                    continue
                closed = (int(recent[-1]["time"])+lengths[profile.timeframe])*1000
                previous = lastbars.get(profile.symbol)
                lastbars[profile.symbol]=closed
                if previous is None or previous==closed or not 0<=now-closed<=10000:
                    continue
                bars = mt5.copy_rates_from_pos(profile.symbol,frames[profile.timeframe],1,900)
                if bars is None:
                    continue
                bars = bars[bars["time"]+lengths[profile.timeframe]<=closed//1000]
                if len(bars)<300 or int(bars[-1]["time"])+lengths[profile.timeframe]!=closed//1000:
                    continue
                result = btc_cross(bars[-100:]) if profile.symbol=="BTCUSD" else ema_pullback(mt5,profile,bars,closed)
                if result:
                    attempt(mt5,profile,login,control,state,day,(closed,*result),sending)
        gbp = PROFILES[2]
        inside = broker.weekday()<5 and lh+timedelta(minutes=30)<=broker<lh+timedelta(hours=2)
        if session_log.get(gbp.symbol)!=(day,inside):
            log.info("GBPUSD ventana activa=%s",inside)
            session_log[gbp.symbol]=(day,inside)
        if inside and not (state/f"GBPUSD-{day}.json").exists():
            decision = fade.poll(mt5,day,now,milliseconds(lh))
            if decision:
                attempt(mt5,gbp,login,control,state,day,decision,sending)
        time.sleep(.25 if inside else 1)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--login",type=int,required=True)
    parser.add_argument("--estado",type=Path,required=True)
    parser.add_argument("--compartido",type=Path,required=True)
    parser.add_argument("--enviar",action="store_true")
    args = parser.parse_args()
    args.estado.mkdir(parents=True,exist_ok=True)
    logging.basicConfig(level=logging.INFO,format="%(asctime)s %(levelname)s %(message)s")
    with bloqueo(args.estado/"ejecucion.lock") as available:
        if not available:
            raise RuntimeError("Ya existe un ejecutor con este estado")
        adapter = CuentaMT5()
        try:
            snapshot = adapter.snapshot()
            mt5 = adapter.mt5
            if not settings.MODO_DEMO or not snapshot or not demo_autorizada(mt5,snapshot[0],args.login):
                raise RuntimeError("Cuenta demo no verificada")
            if args.enviar and not permisos(snapshot[0],mt5.terminal_info()):
                raise RuntimeError("Permisos demo no verificados")
            for profile in PROFILES:
                if not mt5.symbol_select(profile.symbol,True):
                    raise RuntimeError(f"{profile.symbol} no está disponible")
                log.info("%s perfil %s activo",profile.symbol,"demo con órdenes" if args.enviar and profile.sending else "observación")
            run(mt5,adapter,args.login,args.estado,ControlDemo(args.estado,args.compartido),args.enviar)
        finally:
            if adapter.mt5 is not None:
                adapter.mt5.shutdown()


if __name__=="__main__":
    main()
