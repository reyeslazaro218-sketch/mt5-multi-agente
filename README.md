# MT5 Multi-Agente

Bot de trading algorítmico multi-agente para MetaTrader 5 (MQL5 + Python).

## Estructura

```
mt5-multi-agente/
├── README.md
├── .gitignore
├── docs/
│   └── arquitectura.md      # Diseño del sistema
├── mql5/
│   ├── Experts/             # EA principal que orquesta a los agentes
│   ├── Include/             # Clases base: agente, señal, riesgo
│   └── Scripts/             # Utilidades y scripts auxiliares
├── python/
│   ├── agentes/             # Análisis, señal, riesgo, ejecución
│   ├── comunicacion/        # Puente MT5 <-> Python
│   ├── config/              # Configuración
│   └── requirements.txt
├── tests/
└── logs/
```

## Estado

- [x] Fase 1: estructura base
- [ ] Fase 2: puente de comunicación MT5 <-> Python
- [ ] Fase 3: agentes (análisis, señal, riesgo, ejecución)
- [ ] Fase 4: EA orquestador en MQL5
- [ ] Fase 5: pruebas y backtesting

## Aviso

El trading conlleva riesgo de pérdida de capital. Probar siempre en cuenta demo antes de operar en real.

### Sesión demo y recuperación de órdenes

Configura `MT5_PATH` con la ruta al `terminal64.exe` de la instancia que
ejecuta el EA. Inicia sesión en demo y recompila el EA al actualizar Python.
El proceso Python consulta el patrimonio y las posiciones a través de la API
local de MetaTrader 5. La referencia diaria se inicializa en la primera
evaluación de entrada del día UTC, con el mayor de balance y patrimonio.

Si se pierde la respuesta de una orden, se conserva `logs/orden_enviada.json`
y se detienen nuevas entradas. Comprueba órdenes, historial y posiciones en
MT5 antes de resolver manualmente ese registro con el proceso detenido.

### Perfil demo XAUUSD M5

Esta rama usa velas cerradas M5 de XAUUSD, EMA 9/21, RSI 14 y salidas del
bróker con SL a 1,5 ATR y TP a 2,5 ATR. Recompila el EA y utiliza el
orquestador de la misma rama. Ambos componentes deben usar el perfil M5.
El EA obtiene M5 del símbolo configurado independientemente del gráfico
al que se adjunta.
