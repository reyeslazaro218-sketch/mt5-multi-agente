"""Tipos compartidos y clase base de los agentes."""
from dataclasses import dataclass
from typing import Optional


@dataclass
class Analisis:
    simbolo: str
    cierre: float
    ema_rapida: float
    ema_lenta: float
    rsi: float
    atr: float


@dataclass
class Senal:
    simbolo: str
    lado: str  # "BUY" | "SELL"
    precio: float
    atr: float
    motivo: str


@dataclass
class OrdenAprobada:
    simbolo: str
    lado: str
    lote: float
    sl: float
    tp: float


class Agente:
    """Interfaz mínima: cada agente tiene un nombre y procesa una entrada."""
    nombre = "agente"

    def procesar(self, entrada) -> Optional[object]:
        raise NotImplementedError
