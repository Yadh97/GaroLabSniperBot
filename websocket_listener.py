
# Filename: websocket_listener.py

import asyncio
import json
import websockets
from typing import AsyncGenerator

async def listen_new_tokens() -> AsyncGenerator[dict, None]:
    uri = "wss://pumpportal.fun/api/data"
    while True:
        try:
            async with websockets.connect(uri) as ws:
                await ws.send(json.dumps({"method": "subscribeNewToken"}))
                print("[WS] Connected to Pump.fun and subscribed to new tokens.")

                async for raw_msg in ws:
                    try:
                        msg = json.loads(raw_msg)
                        if isinstance(msg, dict) and msg.get("txType") == "create":
                            yield {
                                "name": msg.get("name", "Unknown"),
                                "symbol": msg.get("symbol", "???"),
                                "mint": msg.get("mint"),
                                "marketCapSol": float(msg.get("marketCapSol", 0)),
                                "solAmount": float(msg.get("solAmount", 0)),
                                "uri": msg.get("uri", ""),
                                "trader": msg.get("traderPublicKey", "")
                            }
                    except Exception as parse_err:
                        print(f"[ERROR] Failed to parse message: {parse_err}")
        except Exception as e:
            print(f"[ERROR] WebSocket connection failed: {e}. Retrying in 10 seconds.")
            await asyncio.sleep(10)
