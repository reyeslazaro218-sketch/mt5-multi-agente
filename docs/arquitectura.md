# Arquitectura (borrador Fase 1)

## Visión general

Un EA en MQL5 actúa como orquestador dentro de MT5 y se comunica con agentes en Python mediante un puente (a definir en Fase 2: sockets TCP/ZeroMQ o archivos).

```
MT5 (EA orquestador)  <--->  Puente  <--->  Agentes Python
```

## Agentes

| Agente    | Responsabilidad                                              |
|-----------|--------------------------------------------------------------|
| Análisis  | Procesa datos de mercado e indicadores                       |
| Señal     | Genera señales de compra/venta a partir del análisis         |
| Riesgo    | Valida señales, calcula tamaño de lote, SL/TP, límites diarios |
| Ejecución | Envía órdenes y gestiona posiciones abiertas                 |

## Flujo

1. El EA envía datos de mercado (ticks/velas) al puente.
2. Análisis -> Señal -> Riesgo (puede vetar) -> Ejecución.
3. El EA recibe la orden aprobada y la ejecuta en MT5.

## Decisiones pendientes

- Tecnología del puente (ZeroMQ vs. sockets vs. archivos).
- Formato de mensajes (JSON propuesto).
- Activos y timeframes iniciales.
