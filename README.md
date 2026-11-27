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

### Prueba demo de ventas M5 con filtro H1

`python -m python.demo_ventas_h1 --login LOGIN_DEMO --estado RUTA --offset-broker SEGUNDOS --enviar`
usa la API de MT5 directamente con la cuenta ICMarketsSC-Demo indicada.
Define `MT5_PATH` como la ruta a `terminal64.exe`. Elimina `--enviar` para
probar la lectura y registrar señales sin operar. Usa el desfase observado
entre los timestamps de MT5 y UTC. Si el reloj cambia, la comprobación de
frescura veta las entradas hasta ajustar el parámetro.

No ejecutes en paralelo el orquestador de órdenes en la misma cuenta.
Para detener la prueba crea un archivo vacío `DETENER` en la carpeta de
estado. El proceso deja las posiciones existentes bajo sus SL y TP del
servidor. Si queda un `orden_pendiente.json`, confirma el estado en el
historial de MT5 antes de reanudar.

### Prueba demo USTEC por ticks

Ejecuta `python -m python.demo_ustec --login LOGIN_DEMO --estado RUTA --enviar`
con `MT5_PATH` apuntando al terminal de ICMarketsSC-Demo. Excluye
`--enviar` para registrar señales en observación.

El rango se mide de 09:30 a 09:45 de Nueva York. Una ruptura de dos ticks
seguida de un retorno al rango dentro de 60 segundos habilita una entrada
contraria hasta las 11:00. Se admite un intento de envío por sesión. El stop
usa media amplitud del rango, el objetivo 1,5 R y el cierre por tiempo se
intenta a los 60 minutos. Los límites de riesgo conservan 0,5% por operación
y el freno diario de 2%. Si el mínimo del bróker supera el presupuesto,
se omite la señal.

El archivo `DETENER` dentro de la carpeta de estado detiene este proceso.
Los stops y objetivos siguen en MT5. Mientras el proceso esté apagado,
el cierre local por tiempo queda suspendido.

### Ejecución conjunta de los perfiles demo

Arranca los perfiles USTEC y XAUUSD desde esta misma revisión y pasa el mismo
directorio con `--compartido RUTA` en ambos. Cada perfil necesita su propio
directorio `--estado`. Los dos aplican un freno diario común de 2% y solo
permiten una exposición a la vez. Si queda `orden_compartida.json` en la
carpeta común, se bloquean nuevas entradas hasta conciliar el estado en MT5.

### Perfiles por símbolo en demo

El módulo `python.demo_estudio` requiere los mismos argumentos de cuenta,
estado y carpeta compartida que el perfil USTEC. Con `--enviar` habilita el
retroceso M5 de oro en la mañana de Nueva York, el retroceso M15/H1 de
EURUSD y la ruptura fallida de Londres en GBPUSD. BTCUSD registra cruces
EMA/RSI M1 en observación. Se permite como máximo un intento diario por
símbolo de este módulo y una sola exposición para todos los perfiles.
