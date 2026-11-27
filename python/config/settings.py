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

# --- Estrategia EMA + RSI (M1) -----------------------------------------
EMA_RAPIDA = 9
EMA_LENTA = 21
RSI_PERIODO = 14
RSI_MAX_COMPRA = 70   # no comprar si ya está sobrecomprado
RSI_MIN_VENTA = 30    # no vender si ya está sobrevendido
ATR_PERIODO = 14
SL_ATR_MULT = 1.5
TP_ATR_MULT = 2.5

# --- Dimensionado de lote ----------------------------------------------
# Balance usado hasta que el EA reporte el real (ajústalo al de tu demo).
BALANCE_INICIAL = 10000.0
# Dinero ganado/perdido por 1 lote y 1 unidad de precio. AJUSTAR según las
# especificaciones del contrato de tu broker (tick_value / tick_size).
VALOR_POR_UNIDAD = {
    "BTCUSD": 1.0,
    "XAUUSD": 100.0,
    "EURUSD": 100000.0,
    "NAS100": 1.0,
}
LOTE_MINIMO = 0.01
LOTE_MAXIMO = 1.0
LOTE_PASO = 0.01

# Límite entre el cálculo de riesgo y la recepción en el EA.
ORDEN_VIGENCIA_MS = 3000
DESVIACION_PUNTOS = 10
