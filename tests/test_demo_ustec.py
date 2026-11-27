from datetime import datetime, timezone
from types import SimpleNamespace

from python.demo_ustec import FailedBreakout, clock, make_order, opening_range


def stamp(month, day, hour, minute):
    return datetime(2026, month, day, hour, minute, tzinfo=timezone.utc).timestamp()


def test_cash_open_aligns_across_daylight_saving():
    for month, day, utc_hour in ((10, 19, 13), (11, 9, 14)):
        broker, expected = clock(stamp(month, day, utc_hour, 30))
        assert (broker.hour, broker.minute) == (16, 30)
        assert broker.timestamp() * 1000 == expected


def test_raise_false_breakout_only_on_return_within_minute():
    bot = FailedBreakout(90, 100, .01, True)
    assert bot.update(1000, 100.03) is None
    assert bot.update(2000, 100.01) is None
    assert bot.update(61000, 100) == -1
    assert bot.update(62000, 89.97) is None
    assert bot.update(122001, 90) is None
    assert bot.update(123000, 89.96) is None
    assert bot.update(124000, 90) == 1


def test_mid_session_start_does_not_treat_prior_break_as_new():
    bot = FailedBreakout(90, 100, .01, False)
    assert bot.update(1000, 100.20) is None
    assert bot.update(2000, 100) is None
    assert bot.update(3000, 100.03) is None
    assert bot.update(4000, 100) == -1


def test_opening_range_requires_coverage_at_both_boundaries():
    ticks = [{"time_msc": t, "bid": 90 if t < 450000 else 100, "ask": 92 if t < 450000 else 102}
             for t in range(0, 900000, 500)]
    assert opening_range(ticks, 0, 900000) == (91, 101)
    assert opening_range(ticks[:-100], 0, 900000) is None


def test_order_rounds_down_and_vetoes_excessive_minimum_size():
    mt5 = SimpleNamespace(ORDER_TYPE_BUY=0, ORDER_TYPE_SELL=1, ORDER_FILLING_IOC=2,
                          TRADE_ACTION_DEAL=1, order_calc_profit=lambda *args: -41.0)
    info = SimpleNamespace(trade_tick_size=.01, trade_contract_size=1, volume_step=.1,
                           volume_min=.1, volume_max=100, digits=2, trade_stops_level=0,
                           point=.01, filling_mode=2)
    quote = SimpleNamespace(bid=22000, ask=22001)
    order, reason = make_order(mt5, 881, info, quote, -1, 80)
    assert reason is None and order["volume"] == .1
    assert (order["sl"], order["tp"]) == (22040, 21940)
    order, reason = make_order(mt5, 700, info, quote, -1, 80)
    assert order is None and "lote mínimo" in reason
