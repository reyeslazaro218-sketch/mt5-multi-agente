import pytest

from python.agentes.analisis import AgenteAnalisis, ema, rsi
from python.agentes.base import Analisis, Senal
from python.agentes.riesgo import AgenteRiesgo
from python.agentes.senal import AgenteSenal
from python.config import settings


def vela(simbolo, cierre):
    return {"simbolo": simbolo, "timeframe": "M1", "apertura": cierre,
            "maximo": cierre + 0.5, "minimo": cierre - 0.5,
            "cierre": cierre, "volumen": 100}


def test_ema_constante():
    assert ema([5.0] * 30, 9) == pytest.approx(5.0)


def test_rsi_solo_subidas_es_100():
    assert rsi([float(i) for i in range(40)], 14) == pytest.approx(100.0)


def test_rsi_solo_bajadas_es_0():
    assert rsi([float(100 - i) for i in range(40)], 14) == pytest.approx(0.0)


def test_analisis_necesita_minimo_de_velas():
    ag = AgenteAnalisis()
    assert ag.procesar(vela("EURUSD", 1.1)) is None


def test_analisis_devuelve_resultado_con_datos_suficientes():
    ag = AgenteAnalisis()
    res = None
    for i in range(ag.minimo_velas + 5):
        res = ag.procesar(vela("EURUSD", 1.0 + i * 0.001))
    assert res is not None
    assert res.ema_rapida > res.ema_lenta  # tendencia alcista


def test_senal_cruce_alcista():
    ag = AgenteSenal()
    base = dict(simbolo="EURUSD", cierre=1.1, rsi=50.0, atr=0.001)
    assert ag.procesar(Analisis(ema_rapida=1.0, ema_lenta=1.1, **base)) is None
    s = ag.procesar(Analisis(ema_rapida=1.2, ema_lenta=1.1, **base))
    assert s is not None and s.lado == "BUY"


def test_senal_filtrada_por_rsi():
    ag = AgenteSenal()
    base = dict(simbolo="EURUSD", cierre=1.1, atr=0.001)
    ag.procesar(Analisis(ema_rapida=1.0, ema_lenta=1.1, rsi=80.0, **base))
    assert ag.procesar(Analisis(ema_rapida=1.2, ema_lenta=1.1, rsi=80.0, **base)) is None


def test_riesgo_calcula_sl_tp_y_lote():
    r = AgenteRiesgo(balance_inicial=10000.0)
    o = r.procesar(Senal("EURUSD", "BUY", 1.1, 0.001, "test"))
    assert o is not None
    assert o.sl < 1.1 < o.tp
    assert settings.LOTE_MINIMO <= o.lote <= settings.LOTE_MAXIMO


def test_riesgo_veta_posicion_duplicada():
    r = AgenteRiesgo()
    r.registrar_apertura("EURUSD")
    assert r.procesar(Senal("EURUSD", "BUY", 1.1, 0.001, "test")) is None


def test_riesgo_veta_por_perdida_diaria():
    r = AgenteRiesgo(balance_inicial=10000.0)
    r.actualizar_balance(9000.0)  # -10 %
    assert r.procesar(Senal("EURUSD", "BUY", 1.1, 0.001, "test")) is None
