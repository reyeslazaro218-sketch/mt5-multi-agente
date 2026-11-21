//+------------------------------------------------------------------+
//| EA_Orquestador.mq5                                               |
//| Publica ticks y velas M1 a Python (ZeroMQ PUB) y consulta        |
//| órdenes pendientes (ZeroMQ REQ). Solo opera en cuenta DEMO.      |
//|                                                                  |
//| Dependencia: mql-zmq (https://github.com/dingmaotu/mql-zmq)      |
//|   Copiar Include/Zmq y Library/MT5/libzmq.dll, libsodium.dll     |
//| Activar "Permitir DLL" en las opciones del EA.                   |
//+------------------------------------------------------------------+
#property copyright "mt5-multi-agente"
#property version   "0.10"
#property strict

#include <Zmq/Zmq.mqh>
#include <Trade/Trade.mqh>

input string InpHost          = "127.0.0.1";
input int    InpPuertoDatos   = 5556;   // PUB: MT5 -> Python
input int    InpPuertoComando = 5555;   // REQ: MT5 <-> Python
input bool   InpSoloDemo      = true;   // Bloquea operar en cuenta real
input long   InpMagic         = 20260101;
input int    InpPollMs        = 200;

// Símbolos lógicos: ajusta a los nombres de tu broker en Market Watch
string g_simbolos[] = {"BTCUSD", "XAUUSD", "EURUSD", "NAS100"};

Context  *g_ctx;
Socket   *g_pub;
Socket   *g_req;
CTrade    g_trade;
datetime  g_ultimaVela[];

//+------------------------------------------------------------------+
int OnInit()
{
   if(InpSoloDemo && AccountInfoInteger(ACCOUNT_TRADE_MODE) != ACCOUNT_TRADE_MODE_DEMO)
   {
      Print("BLOQUEADO: InpSoloDemo=true y la cuenta no es demo.");
      return INIT_FAILED;
   }

   g_ctx = new Context("orquestador");
   g_pub = new Socket(g_ctx, ZMQ_PUB);
   g_req = new Socket(g_ctx, ZMQ_REQ);
   g_pub.bind(StringFormat("tcp://%s:%d", InpHost, InpPuertoDatos));
   g_req.connect(StringFormat("tcp://%s:%d", InpHost, InpPuertoComando));
   g_req.setReceiveTimeout(100);
   g_req.setSendTimeout(100);

   int n = ArraySize(g_simbolos);
   ArrayResize(g_ultimaVela, n);
   ArrayInitialize(g_ultimaVela, 0);
   for(int i = 0; i < n; i++)
      SymbolSelect(g_simbolos[i], true);

   g_trade.SetExpertMagicNumber(InpMagic);
   EventSetMillisecondTimer(InpPollMs);
   Print("EA_Orquestador iniciado (demo=", InpSoloDemo, ")");
   return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   EventKillTimer();
   if(CheckPointer(g_pub) == POINTER_DYNAMIC) delete g_pub;
   if(CheckPointer(g_req) == POINTER_DYNAMIC) delete g_req;
   if(CheckPointer(g_ctx) == POINTER_DYNAMIC) delete g_ctx;
}

//+------------------------------------------------------------------+
//| Publica datos de todos los símbolos en cada timer                |
//+------------------------------------------------------------------+
void OnTimer()
{
   PublicarDatos();
   ConsultarOrdenes();
}

void PublicarDatos()
{
   for(int i = 0; i < ArraySize(g_simbolos); i++)
   {
      string s = g_simbolos[i];
      MqlTick t;
      if(!SymbolInfoTick(s, t)) continue;

      string tick = StringFormat(
         "{\"tipo\":\"tick\",\"version\":1,\"ts\":%I64d,\"simbolo\":\"%s\",\"bid\":%.8f,\"ask\":%.8f}",
         (long)t.time_msc, s, t.bid, t.ask);
      ZmqMsg m(tick);
      g_pub.send(m, true);

      // Vela M1 cerrada (índice 1)
      datetime tv = iTime(s, PERIOD_M1, 1);
      if(tv != 0 && tv != g_ultimaVela[i])
      {
         g_ultimaVela[i] = tv;
         string vela = StringFormat(
            "{\"tipo\":\"vela\",\"version\":1,\"ts\":%I64d,\"simbolo\":\"%s\",\"timeframe\":\"M1\","
            "\"apertura\":%.8f,\"maximo\":%.8f,\"minimo\":%.8f,\"cierre\":%.8f,\"volumen\":%I64d}",
            (long)tv * 1000, s,
            iOpen(s, PERIOD_M1, 1), iHigh(s, PERIOD_M1, 1),
            iLow(s, PERIOD_M1, 1),  iClose(s, PERIOD_M1, 1),
            iTickVolume(s, PERIOD_M1, 1));
         ZmqMsg mv(vela);
         g_pub.send(mv, true);
      }
   }
}

//+------------------------------------------------------------------+
//| Poll: pide a Python la orden pendiente y la ejecuta              |
//+------------------------------------------------------------------+
void ConsultarOrdenes()
{
   ZmqMsg poll("{}");
   if(!g_req.send(poll)) return;

   ZmqMsg resp;
   if(!g_req.recv(resp)) return;
   string txt = resp.getData();
   if(StringLen(txt) < 5) return;          // "{}" = sin órdenes

   if(StringFind(txt, "\"tipo\":\"orden\"") < 0) return;

   string simbolo = ExtraerTexto(txt, "simbolo");
   string lado    = ExtraerTexto(txt, "lado");
   double lote    = ExtraerNumero(txt, "lote");
   double sl      = ExtraerNumero(txt, "sl");
   double tp      = ExtraerNumero(txt, "tp");

   bool ok = false;
   if(lado == "BUY")        ok = g_trade.Buy(lote, simbolo, 0, sl, tp, "multi-agente");
   else if(lado == "SELL")  ok = g_trade.Sell(lote, simbolo, 0, sl, tp, "multi-agente");
   else if(lado == "CLOSE") ok = CerrarPosiciones(simbolo);

   Print("Orden ", lado, " ", simbolo, " lote=", lote, " ok=", ok,
         " retcode=", g_trade.ResultRetcode());
}

bool CerrarPosiciones(const string simbolo)
{
   bool todo = true;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong tk = PositionGetTicket(i);
      if(PositionGetString(POSITION_SYMBOL) == simbolo &&
         PositionGetInteger(POSITION_MAGIC) == InpMagic)
         todo = g_trade.PositionClose(tk) && todo;
   }
   return todo;
}

//+------------------------------------------------------------------+
//| Extracción mínima de campos JSON (suficiente para este esquema)  |
//+------------------------------------------------------------------+
string ExtraerTexto(const string json, const string clave)
{
   string k = "\"" + clave + "\":\"";
   int p = StringFind(json, k);
   if(p < 0) return "";
   p += StringLen(k);
   int q = StringFind(json, "\"", p);
   return (q < 0) ? "" : StringSubstr(json, p, q - p);
}

double ExtraerNumero(const string json, const string clave)
{
   string k = "\"" + clave + "\":";
   int p = StringFind(json, k);
   if(p < 0) return 0.0;
   p += StringLen(k);
   int q = p;
   while(q < StringLen(json))
   {
      ushort c = StringGetCharacter(json, q);
      if(c == ',' || c == '}') break;
      q++;
   }
   return StringToDouble(StringSubstr(json, p, q - p));
}
//+------------------------------------------------------------------+
