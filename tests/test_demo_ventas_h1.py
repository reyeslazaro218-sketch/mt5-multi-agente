from types import SimpleNamespace
from unittest.mock import Mock

from python.demo_ventas_h1 import confirmar_venta, demo_autorizada


def test_h1_usa_solo_velas_cerradas_al_cierre_m5():
    velas = [{"time": i * 3600, "close": 100 - i / 2} for i in range(60)]
    velas.append({"time": 60 * 3600, "close": 500})
    venta = SimpleNamespace(lado="SELL")
    assert confirmar_venta(venta, velas, 60 * 3600)
    assert not confirmar_venta(venta, velas, 61 * 3600)
    assert not confirmar_venta(venta, velas[:-1], 61 * 3600)


def test_ignora_compras_y_historico_insuficiente():
    velas = [{"time": i * 3600, "close": 100 - i / 2} for i in range(60)]
    assert not confirmar_venta(SimpleNamespace(lado="BUY"), velas, 60 * 3600)
    assert not confirmar_venta(SimpleNamespace(lado="SELL"), velas[:10], 10 * 3600)


def test_cuenta_demo_fijada_por_login_y_servidor():
    mt5 = Mock(ACCOUNT_TRADE_MODE_DEMO=0)
    cuenta = SimpleNamespace(trade_mode=0, login=1, server="ICMarketsSC-Demo")
    assert demo_autorizada(mt5, cuenta, 1)
    assert not demo_autorizada(mt5, cuenta, 2)
    cuenta.trade_mode = 2
    assert not demo_autorizada(mt5, cuenta, 1)
