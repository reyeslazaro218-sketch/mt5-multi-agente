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
