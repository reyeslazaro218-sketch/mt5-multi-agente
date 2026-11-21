# -*- coding: utf-8 -*-
import json
import sys
import MetaTrader5 as mt5


def send(data):
    sys.stdout.write(json.dumps(data) + "\n")
    sys.stdout.flush()


def read_request():
    line = sys.stdin.readline()
    if not line:
        return None
    return json.loads(line)


def handle(method, params):
    if method == "initialize":
        if not mt5.initialize():
            return {"error": "No se pudo inicializar MT5: " + str(mt5.last_error())}
        return {"ok": True, "version": mt5.version()}

    if method == "tools/list":
        return {
            "tools": [
                {
                    "name": "mt5_get_account",
                    "description": "Obtiene información de la cuenta de MT5",
                    "inputSchema": {"type": "object", "properties": {}}
                },
                {
                    "name": "mt5_get_rates",
                    "description": "Obtiene velas (OHLC) de un símbolo",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "symbol": {"type": "string"},
                            "timeframe": {"type": "string", "description": "M1,M5,M15,M30,H1,H4,D1"},
                            "count": {"type": "integer"}
                        },
                        "required": ["symbol"]
                    }
                },
                {
                    "name": "mt5_get_symbols",
                    "description": "Lista los símbolos disponibles",
                    "inputSchema": {"type": "object", "properties": {}}
                }
            ]
        }

    if method == "tools/call":
        name = params.get("name")
        args = params.get("arguments", {})

        if name == "mt5_get_account":
            info = mt5.account_info()
            if info is None:
                return {"error": str(mt5.last_error())}
            return info._asdict()

        if name == "mt5_get_symbols":
            syms = mt5.symbols_get()
            return {"symbols": [s.name for s in syms] if syms else []}

        if name == "mt5_get_rates":
            symbol = args.get("symbol")
            tf_map = {
                "M1": mt5.TIMEFRAME_M1,
                "M5": mt5.TIMEFRAME_M5,
                "M15": mt5.TIMEFRAME_M15,
                "M30": mt5.TIMEFRAME_M30,
                "H1": mt5.TIMEFRAME_H1,
                "H4": mt5.TIMEFRAME_H4,
                "D1": mt5.TIMEFRAME_D1,
            }
            tf = tf_map.get(args.get("timeframe", "H1"), mt5.TIMEFRAME_H1)
            count = args.get("count", 100)
            rates = mt5.copy_rates_from_pos(symbol, tf, 0, count)
            if rates is None:
                return {"error": str(mt5.last_error())}
            return {"rates": rates.tolist()}

        return {"error": "Herramienta desconocida: " + str(name)}

    return {"error": "Método desconocido"}


def main():
    while True:
        req = read_request()
        if req is None:
            break
        response = handle(req.get("method"), req.get("params", {}))
        send({"id": req.get("id"), "result": response})


if __name__ == "__main__":
    main()