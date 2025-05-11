# Filename: main.py

import asyncio
import time
from websocket_listener import listen_new_tokens
from token_cache import add_token_if_new, cleanup_expired_tokens, token_cache
from token_monitor import recheck_tokens_loop
import config

# Central stats tracker
stats = {
    "start_time": time.time(),
    "token_count": 0,
    "last_token": None,
    "last_cleanup": None,
}


async def consume_tokens():
    """
    Listen to Pump.fun for new tokens and add to cache.
    """
    async for token in listen_new_tokens():
        if token:
            print(f"[WS] New token from Pump.fun: {token['symbol']} ({token['mint']})")
            add_token_if_new(token['mint'], token)
            stats["token_count"] += 1
            stats["last_token"] = {
                "symbol": token['symbol'],
                "mint": token['mint'],
                "timestamp": time.strftime("%H:%M:%S")
            }


async def cleanup_loop():
    """
    Periodically remove expired tokens from memory cache.
    """
    while True:
        cleanup_expired_tokens()
        stats["last_cleanup"] = time.strftime("%H:%M:%S")
        await asyncio.sleep(config.CACHE_CLEANUP_INTERVAL_SECONDS)


async def log_stats_loop():
    """
    Console dashboard to monitor bot health and performance every minute.
    """
    while True:
        uptime = int(time.time() - stats["start_time"])
        hours, rem = divmod(uptime, 3600)
        minutes, seconds = divmod(rem, 60)
        uptime_str = f"{hours:02}:{minutes:02}:{seconds:02}"

        print("\n==============================")
        print(f"🧠 BOT STATUS REPORT")
        print(f"⏱️ Uptime: {uptime_str}")
        print(f"📦 Tokens Seen: {stats['token_count']}")
        print(f"🧠 Current Cache Size: {len(token_cache)}")
        if stats['last_token']:
            print(f"🆕 Last Token: {stats['last_token']['symbol']} at {stats['last_token']['timestamp']}")
        if stats['last_cleanup']:
            print(f"🧹 Last Cleanup: {stats['last_cleanup']}")
        print("==============================\n")

        await asyncio.sleep(60)


async def main():
    print("[INFO] Solana Sniper Bot started. Tracking tokens in real time.")
    await asyncio.gather(
        consume_tokens(),
        cleanup_loop(),
        log_stats_loop(),
        recheck_tokens_loop()
    )

if __name__ == "__main__":
    asyncio.run(main())
