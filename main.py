# Filename: main.py

import asyncio
import json
import websockets
import time
from filters import basic_filter, rugcheck_filter, holders_distribution_filter
from trader import attempt_buy_token
from telegram_alert import send_token_alert
from token_cache import TokenCache
from models import TokenInfo
import config

# Initialize token memory cache
cache = TokenCache()

async def process_new_token_event(event_data):
    token_address = event_data.get("tokenAddress")
    symbol = event_data.get("symbol", "UNKNOWN")
    print(f"[WS] New token detected: {symbol} ({token_address})")
    cache.add_token(token_address)

async def recheck_tokens_loop():
    # Periodically re-check tracked tokens for filter conditions or purge criteria.
    while True:
        due_tokens = cache.get_due_for_check(interval=300)  # Every 5 minutes
        print(f"[RECHECK] {len(due_tokens)} tokens due for recheck.")
        for token_state in due_tokens:
            token_addr = token_state.address

            # Simulate fetching updated token info (e.g. via Moralis or Jupiter or Dex APIs)
            token_info = fetch_token_info_simulated(token_addr)
            if not token_info:
                continue

            # Evaluate filters again
            if all([
                basic_filter(token_info),
                rugcheck_filter(token_info.address),
                holders_distribution_filter(token_info.address)
            ]):
                print(f"[RECHECK ✅] Token {token_info.symbol} now qualifies!")
                send_token_alert(token_info)
                if config.AUTO_BUY_ENABLED:
                    attempt_buy_token(token_info)
            cache.update_check(token_addr, signal_strength=1)
        # Purge old inactive tokens
        to_remove = cache.get_ready_for_purge()
        for dead in to_remove:
            print(f"[PURGE] Removing inactive token: {dead}")
            cache.remove_token(dead)
        await asyncio.sleep(300)  # Every 5 min

def fetch_token_info_simulated(token_addr):
    # Simulated placeholder for fetching updated info about a token.
    return TokenInfo(
        address=token_addr,
        name="TestToken",
        symbol="TEST",
        price_usd=0.001,
        liquidity_usd=21000,
        fdv=100000,
        pair_id="simulated123",
        source="pumpfun"
    )

async def websocket_listener():
    uri = "wss://pumpportal.fun/api/data"
    while True:
        try:
            async with websockets.connect(uri) as ws:
                await ws.send(json.dumps({"method": "subscribeNewToken"}))
                print("[WS] Listening for new tokens...")
                async for message in ws:
                    try:
                        event = json.loads(message)
                        await process_new_token_event(event)
                    except Exception as e:
                        print(f"[ERROR] Failed to handle websocket message: {e}")
        except Exception as e:
            print(f"[ERROR] WebSocket connection failed: {e}")
            await asyncio.sleep(10)

def main():
    print("[INFO] Solana Sniper Bot started. Auto-buy is ON" if config.AUTO_BUY_ENABLED else "Auto-buy is OFF")
    loop = asyncio.get_event_loop()
    tasks = [
        loop.create_task(websocket_listener()),
        loop.create_task(recheck_tokens_loop())
    ]
    loop.run_until_complete(asyncio.wait(tasks))

if __name__ == "__main__":
    main()
