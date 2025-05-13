import asyncio
import json
import threading
import websockets
from typing import Callable
import config

class WebSocketListener:
    def __init__(self, on_token_callback: Callable[[dict], None]):
        self.uri = config.RPC_WEBSOCKET_ENDPOINT
        self.on_token_callback = on_token_callback
        self._stop_event = threading.Event()

    def stop(self):
        self._stop_event.set()

    async def _connect(self):
        try:
            async with websockets.connect(self.uri) as ws:
                await ws.send(json.dumps({"method": "subscribeNewToken"}))
                print("[WS] Connected and subscribed to new tokens")
                async for raw_msg in ws:
                    if self._stop_event.is_set():
                        break
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
                            self.on_token_callback(token_info)
                    except Exception as e:
                        print(f"[ERROR] Failed to parse token message: {e}")
        except Exception as e:
            print(f"[ERROR] WebSocket connection error: {e}")
            await asyncio.sleep(5)
            await self._connect()

    def run(self):
        asyncio.run(self._connect())
