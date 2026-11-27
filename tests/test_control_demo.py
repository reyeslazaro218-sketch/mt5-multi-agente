from types import SimpleNamespace
from unittest.mock import Mock

from python.comunicacion.control_demo import ControlDemo


def test_solo_un_proceso_puede_preparar_una_entrada(tmp_path):
    shared = tmp_path / "cuenta"
    primero = ControlDemo(tmp_path / "a", shared)
    segundo = ControlDemo(tmp_path / "b", shared)
    with primero.entrada() as disponible:
        assert disponible
        with segundo.entrada() as concurrente:
            assert not concurrente
    with segundo.entrada() as disponible:
        assert disponible


def test_orden_incierta_bloquea_ambos_perfiles(tmp_path):
    shared = tmp_path / "cuenta"
    a = ControlDemo(tmp_path / "a", shared)
    b = ControlDemo(tmp_path / "b", shared)
    mt5 = Mock()
    mt5.order_send.return_value = None
    with a.entrada() as disponible:
        assert disponible
        assert a.enviar(mt5, {"symbol": "USTEC"}) is None
    with b.entrada() as disponible:
        assert not disponible
    mt5.order_send.assert_called_once()


def test_freno_diario_compartido(tmp_path):
    shared = tmp_path / "cuenta"
    a = ControlDemo(tmp_path / "a", shared)
    b = ControlDemo(tmp_path / "b", shared)
    cuenta = SimpleNamespace(login=1, server="Demo", equity=1000., balance=1000.)
    assert a.riesgo(cuenta)
    cuenta.equity = 975.
    assert not b.riesgo(cuenta)
    cuenta.equity = 1000.
    assert not a.riesgo(cuenta)
