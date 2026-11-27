from datetime import datetime, timezone
from unittest.mock import Mock

import numpy as np

from python.demo_estudio import PROFILES, attempt, london_hour, period_atr
from python.demo_ustec import FailedBreakout, clock


def test_londres_usa_su_propio_cambio_a_hora_de_invierno():
    for day, hour in ((23, 10), (26, 11)):
        utc = datetime(2026, 10, day, 12, tzinfo=timezone.utc).timestamp()
        broker, _ = clock(utc)
        assert london_hour(broker, utc) == hour
    utc = datetime(2026, 11, 2, 12, tzinfo=timezone.utc).timestamp()
    broker, _ = clock(utc)
    assert london_hour(broker, utc) == 10


def test_gbp_configura_pip_y_ventana_de_dos_minutos():
    f = FailedBreakout(1.20, 1.21, .00001, True, buffer=.0001, return_ms=120000)
    assert f.update(1000, 1.21005) is None
    assert f.update(2000, 1.21011) is None
    assert f.update(115000, 1.21) == -1


def test_atr_incluye_salto_desde_cierre_anterior():
    close = np.r_[100., np.full(14, 104.)]
    bars = {"close": close, "high": close + 1, "low": close - 1}
    assert period_atr(bars) == (5+13*2)/14


def test_btc_en_observacion_no_consulta_ni_envia_orden(tmp_path):
    terminal, control = Mock(), Mock()
    btc = next(p for p in PROFILES if p.symbol=="BTCUSD")
    attempt(terminal, btc, 1, control, tmp_path, "2026-11-27", (1,1,10.), True)
    terminal.order_send.assert_not_called()
    control.entrada.assert_not_called()
