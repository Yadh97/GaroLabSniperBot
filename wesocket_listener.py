import asyncio
import json
import websockets
from typing import AsyncGenerator

async def listen_new_tokens() -> AsyncGenerator[dict, None]:
    uri = "wss://pumpportal.fun/api/data"
    try:
        async with websockets.connect(uri) as ws:
            await ws.send(json.dumps({"method": "subscribeNewToken"}))
            print("[INFO] Connected to Pump.fun WebSocket and subscribed to new tokens")

            async for raw_msg in ws:
                try:
                    msg = json.loads(raw_msg)
                    if isinstance(msg, dict) and msg.get("txType") == "create":
                        token_info = {
                            "name": msg.get("name", "Unknown"),
                            "symbol": msg.get("symbol", "???"),
                            "mint": msg.get("mint"),
                            "marketCapSol": float(msg.get("marketCapSol", 0)),
                            "solAmount": float(msg.get("solAmount", 0)),
                            "uri": msg.get("uri", ""),
                            "trader": msg.get("traderPublicKey", "")
                        }
                        yield token_info
                except Exception as e:
                    print(f"[ERROR] Failed to parse token message: {e}")
    except Exception as e:
        print(f"[ERROR] WebSocket connection error: {e}")
        while True:
            await asyncio.sleep(5)
            yield None  # Yielding None as heartbeat or failure flag
