# websocket_listener.py

import asyncio
import json
import threading
import websockets
from queue import Queue

class WebSocketListener:
    def __init__(self, uri: str, event_queue: Queue):
        self.uri = uri
        self.event_queue = event_queue
        self.connected = False

    async def _handler(self):
        while True:
            try:
                async with websockets.connect(self.uri) as ws:
                    self.connected = True
                    await ws.send(json.dumps({"method": "subscribeNewToken"}))
                    print("[WS] Connected and subscribed to new tokens.")

                    async for raw_msg in ws:
                        try:
                            msg = json.loads(raw_msg)
                            if isinstance(msg, dict) and msg.get("txType") == "create":
                                token_info = {
                                    "mint": msg.get("mint"),
                                    "symbol": msg.get("symbol", "???"),
                                    "name": msg.get("name", "Unknown"),
                                    "marketCapSol": float(msg.get("marketCapSol", 0)),
                                    "solAmount": float(msg.get("solAmount", 0)),
                                    "uri": msg.get("uri", ""),
                                    "trader": msg.get("traderPublicKey", "")
                                }
                                self.event_queue.put(token_info)
                        except Exception as e:
                            print(f"[ERROR] Failed to parse message: {e}")
            except Exception as e:
                self.connected = False
                print(f"[ERROR] WebSocket connection failed: {e}")
                print("[INFO] Reconnecting in 5 seconds...")
                await asyncio.sleep(5)

    def run(self):
        asyncio.run(self._handler())
