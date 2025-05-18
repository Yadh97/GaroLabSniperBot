# Filename: main.py

import time
import threading
import asyncio
from websocket_listener import WebSocketListener
from token_cache import (
    add_token_if_new,
    update_check,
    get_due_for_check,
    get_ready_for_purge,
    remove_token,
    token_cache,
    cleanup_expired_tokens,
)
from telegram_alert import send_token_alert
from filters import basic_filter, holders_distribution_filter
from trader import attempt_buy_token
from models import TokenInfo
import config

# ====== Runtime Stats ======
stats = {
    "start_time": time.time(),
    "token_count": 0,
    "last_token": None,
    "last_cleanup": None,
    "qualified": 0,
    "alerts_sent": 0,
}


# ====== Handle Token Creation Event ======
def handle_new_token(event: dict):
    mint = event.get("mint")
    symbol = event.get("symbol", "???")
    if not mint:
        print("[WARN] Missing mint address.")
        return

    print(f"[WS] New token from Pump.fun: {symbol} ({mint})")
    add_token_if_new(mint, event)

    try:
        token_obj = TokenInfo(
            address=mint,
            name=event.get("name", "Unknown"),
            symbol=symbol,
            price_usd=0.001,
            liquidity_usd=event.get("solAmount", 0) * config.SOL_PRICE_USD,
            fdv=event.get("marketCapSol", 0) * config.SOL_PRICE_USD,
            pair_id="",
            source="pumpfun"
        )

        if all([
            basic_filter(token_obj),
            holders_distribution_filter(token_obj.address),
        ]):
            print(f"[✅ FILTER PASS] {symbol} qualifies!")
            stats["qualified"] += 1
            send_token_alert(token_obj)
            stats["alerts_sent"] += 1

            if config.AUTO_BUY_ENABLED:
                attempt_buy_token(token_obj)

            update_check(mint, signal_strength=1)
        else:
            update_check(mint, signal_strength=0)

    except Exception as e:
        print(f"[ERROR] Token {mint} processing failed: {e}")

    stats["token_count"] += 1
    stats["last_token"] = {
        "symbol": symbol,
        "mint": mint,
        "timestamp": time.strftime("%H:%M:%S")
    }


# ====== Recheck Loop ======
async def recheck_tokens_loop():
    while True:
        due_tokens = get_due_for_check(interval=300)
        print(f"[RECHECK] {len(due_tokens)} tokens due for check.")
        for entry in due_tokens:
            mint = entry["address"]
            event = entry["data"]
            try:
                token_obj = TokenInfo(
                    address=mint,
                    name=event.get("name", "Unknown"),
                    symbol=event.get("symbol", "???"),
                    price_usd=0.001,
                    liquidity_usd=event.get("solAmount", 0) * config.SOL_PRICE_USD,
                    fdv=event.get("marketCapSol", 0) * config.SOL_PRICE_USD,
                    pair_id="",
                    source="pumpfun"
                )

                if all([
                    basic_filter(token_obj),
                    holders_distribution_filter(token_obj.address),
                ]):
                    print(f"[RECHECK ✅] {token_obj.symbol} now qualifies!")
                    send_token_alert(token_obj)
                    stats["alerts_sent"] += 1

                    if config.AUTO_BUY_ENABLED:
                        attempt_buy_token(token_obj)

                    update_check(mint, signal_strength=1)
                else:
                    update_check(mint, signal_strength=0)
            except Exception as e:
                print(f"[RECHECK ERROR] {mint}: {e}")

        await asyncio.sleep(300)


# ====== Cleanup Loop ======
async def cleanup_loop():
    while True:
        cleanup_expired_tokens()
        stats["last_cleanup"] = time.strftime("%H:%M:%S")
        await asyncio.sleep(config.CACHE_CLEANUP_INTERVAL_SECONDS)


# ====== Logging Loop ======
async def log_stats_loop():
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
        print(f"✅ Qualified Tokens: {stats['qualified']}")
        print(f"📣 Alerts Sent: {stats['alerts_sent']}")
        if stats['last_token']:
            print(f"🆕 Last Token: {stats['last_token']['symbol']} at {stats['last_token']['timestamp']}")
        if stats['last_cleanup']:
            print(f"🧹 Last Cleanup: {stats['last_cleanup']}")
        print("==============================\n")
        await asyncio.sleep(60)


# ====== Entrypoint ======
def main():
    print("[INFO] Starting Solana Sniper Bot...")

    # Start WebSocket listener in background thread
    ws_listener = WebSocketListener(on_token_callback=handle_new_token)
    ws_thread = threading.Thread(target=ws_listener.run, name="ws_listener", daemon=True)
    ws_thread.start()

    # Async Loops
    loop = asyncio.get_event_loop()
    loop.run_until_complete(asyncio.gather(
        recheck_tokens_loop(),
        cleanup_loop(),
        log_stats_loop(),
    ))


if __name__ == "__main__":
    main()
