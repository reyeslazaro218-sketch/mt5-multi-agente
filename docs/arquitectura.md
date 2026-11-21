# Arquitectura

## Visión general

Un EA en MQL5 actúa como orquestador dentro de MT5 y se comunica con los agentes en Python mediante **ZeroMQ** con mensajes **JSON**.

```
MT5 (EA_Orquestador)
   PUB :5556  ------ ticks / velas M1 ------>  SUB  Python
   REQ :5555  <----- orden pendiente --------  REP  Python
```

- **PUB/SUB (puerto 5556):** el EA publica ticks y velas M1 cerradas.
- **REQ/REP (puerto 5555):** el EA hace *poll* cada 200 ms; Python responde con la orden pendiente o `{}`. El EA inicia siempre la conexión, así Python nunca bloquea al EA.

## Decisiones tomadas

| Tema             | Decisión                                                  |
|------------------|-----------------------------------------------------------|
| Puente           | ZeroMQ (librería `mql-zmq` en el lado MQL5)               |
| Formato          | JSON, campo `version` = 1                                 |
| Timeframe        | M1                                                        |
| Activos          | Bitcoin, Oro, EURUSD, NAS100 (ampliable a otros operables en M1) |
| Cuenta           | **Demo** (el EA se niega a iniciar en cuenta real con `InpSoloDemo=true`) |

Los nombres reales de símbolo dependen del broker; se configuran en `python/config/settings.py` y en el array `g_simbolos` del EA.

## Protocolo de mensajes

Todos incluyen `tipo`, `version`, `ts` (epoch ms).

| Tipo        | Sentido         | Campos                                                        |
|-------------|-----------------|---------------------------------------------------------------|
| `tick`      | MT5 -> Python   | simbolo, bid, ask                                             |
| `vela`      | MT5 -> Python   | simbolo, timeframe, apertura, maximo, minimo, cierre, volumen |
| `orden`     | Python -> MT5   | simbolo, lado (BUY/SELL/CLOSE), lote, sl, tp                  |
| `respuesta` | MT5 -> Python   | ok, ticket, error                                             |

Validación en `python/comunicacion/mensajes.py`.

## Agentes

| Agente    | Responsabilidad                                              |
|-----------|--------------------------------------------------------------|
| Análisis  | Procesa datos de mercado e indicadores                       |
| Señal     | Genera señales de compra/venta a partir del análisis         |
| Riesgo    | Valida señales, calcula tamaño de lote, SL/TP, límites diarios |
| Ejecución | Envía órdenes y gestiona posiciones abiertas                 |

## Flujo

1. El EA publica ticks/velas M1.
2. Análisis -> Señal -> Riesgo (puede vetar) -> Ejecución.
3. Ejecución encola la orden en el servidor; el EA la recoge en su siguiente poll y la ejecuta.

## Pendiente (Fase 3)

- Implementar los cuatro agentes en `python/agentes/`.
- El EA aún no devuelve el mensaje `respuesta` (ticket/error) a Python.
- Pruebas de integración con MT5 en demo.
