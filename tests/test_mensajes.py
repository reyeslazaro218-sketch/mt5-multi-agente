import json

import pytest

from python.comunicacion import mensajes


def test_tick_valido_ida_y_vuelta():
    texto = mensajes.crear("tick", simbolo="EURUSD", bid=1.0851, ask=1.0853)
    msg = mensajes.decodificar(texto)
    assert msg["tipo"] == "tick" and msg["simbolo"] == "EURUSD"


def test_orden_valida():
    texto = mensajes.crear("orden", simbolo="XAUUSD", lado="BUY", lote=0.1, sl=2300.0, tp=2330.0)
    assert mensajes.decodificar(texto)["lado"] == "BUY"


def test_orden_lado_invalido():
    with pytest.raises(mensajes.MensajeInvalido):
        mensajes.crear("orden", simbolo="XAUUSD", lado="HOLD", lote=0.1, sl=0, tp=0)


def test_orden_lote_cero():
    with pytest.raises(mensajes.MensajeInvalido):
        mensajes.crear("orden", simbolo="XAUUSD", lado="BUY", lote=0, sl=0, tp=0)


def test_faltan_campos():
    with pytest.raises(mensajes.MensajeInvalido):
        mensajes.crear("tick", simbolo="EURUSD", bid=1.0)


def test_tipo_desconocido():
    with pytest.raises(mensajes.MensajeInvalido):
        mensajes.decodificar(json.dumps({"tipo": "x", "version": 1}))


def test_json_roto():
    with pytest.raises(mensajes.MensajeInvalido):
        mensajes.decodificar("{no es json")
