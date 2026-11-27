import json
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

from python.agentes.analisis import AgenteAnalisis, rsi
from python.comunicacion import mensajes
from python.comunicacion.servidor_zmq import ServidorZMQ
from python.orquestador import Orquestador


def test_rechazo_libera_solicitud_y_no_reenvia_orden(tmp_path):
    servidor = ServidorZMQ(puerto_datos=5569, puerto_comandos=0, diario=tmp_path / "orden.json")
    try:
        solicitud = uuid4().hex
        servidor.enviar_orden(simbolo="EURUSD", lado="BUY", lote=.01, sl=1, tp=2,
                              solicitud=solicitud, cuenta=1, servidor="Demo")
        rep = Mock()
        real = servidor.rep
        servidor.rep = rep
        real.close()
        rep.recv_string.return_value = "{}"
        servidor._procesar_comando()
        assert json.loads(rep.send_string.call_args.args[0])["solicitud"] == solicitud
        assert servidor.diario.exists()
        servidor._procesar_comando()
        rep.send_string.assert_called_with("{}")
        rep.recv_string.return_value = mensajes.crear("respuesta", solicitud=solicitud,
                                                       ok=False, ticket=0, error="rechazo")
        servidor._procesar_comando()
        assert not servidor.orden_en_curso
        assert not servidor.diario.exists()
    finally:
        servidor.rep.close()
        servidor.sub.close()


def test_freno_diario_persiste(tmp_path):
    cuenta = SimpleNamespace(login=1, server="Demo", equity=1000., balance=1000.)
    primero = Orquestador(servidor=Mock(), estado_dir=tmp_path)
    assert primero.riesgo_disponible(cuenta)
    cuenta.equity = 970.
    assert not primero.riesgo_disponible(cuenta)
    cuenta.equity = 1020.
    segundo = Orquestador(servidor=Mock(), estado_dir=tmp_path)
    assert not segundo.riesgo_disponible(cuenta)


def test_duplicados_huecos_y_rsi_plano():
    agente = AgenteAnalisis()
    vela = {"simbolo": "EURUSD", "ts": 60_000}
    agente.procesar(vela)
    agente.procesar(vela)
    assert len(agente.velas["EURUSD"]) == 1
    agente.procesar(dict(vela, ts=120_000))
    assert len(agente.velas["EURUSD"]) == 2
    agente.procesar(dict(vela, ts=240_000))
    assert len(agente.velas["EURUSD"]) == 1
    assert rsi([1.] * 20, 14) == 50
