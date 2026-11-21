"""Configuración central del bot multi-agente.

Los nombres de símbolo varían según el broker (sufijos como ".r", "m", "#").
Ajusta SIMBOLOS_BROKER a los nombres reales de tu Market Watch en MT5.
"""

# --- Modo de operación -------------------------------------------------
MODO_DEMO = True  # NO cambiar a False hasta validar en demo de forma sostenida

# --- Mercado -----------------------------------------------------------
TIMEFRAME = "M1"

# Nombre lógico -> nombre real en el broker
SIMBOLOS_BROKER = {
    "BITCOIN": "BTCUSD",
    "ORO": "XAUUSD",
    "EURUSD": "EURUSD",
    "NAS100": "NAS100",
}

# --- Puente ZeroMQ -----------------------------------------------------
ZMQ_HOST = "127.0.0.1"
ZMQ_PUERTO_COMANDOS = 5555   # REP (Python) <-> REQ (MT5): órdenes y respuestas
ZMQ_PUERTO_DATOS = 5556      # PUB (MT5) -> SUB (Python): ticks y velas

# --- Riesgo (valores iniciales conservadores) --------------------------
RIESGO_POR_OPERACION_PCT = 0.5
PERDIDA_MAXIMA_DIARIA_PCT = 2.0
MAX_POSICIONES_ABIERTAS = 4
