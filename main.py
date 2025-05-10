# main.py

import asyncio
from websocket_listener import listen_new_tokens
from token_cache import add_token_if_new, cleanup_expired_tokens
import config

async def consume_tokens():
    async for token in listen_new_tokens():
        if token:
            print(f"[WS] New token from Pump.fun: {token['symbol']} ({token['mint']})")
            add_token_if_new(token['mint'], token)

async def cleanup_loop():
    while True:
        cleanup_expired_tokens()
        await asyncio.sleep(config.CACHE_CLEANUP_INTERVAL_SECONDS)

async def main():
    print("[INFO] Solana Sniper Bot started.")
    await asyncio.gather(
        consume_tokens(),
        cleanup_loop()
    )

if __name__ == "__main__":
    asyncio.run(main())
