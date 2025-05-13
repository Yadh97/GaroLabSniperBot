# main.py

import time
import threading
from websocket_listener import WebSocketListener
from token_cache import (
    add_token_if_new,
    cleanup_expired_tokens,
    get_due_for_check,
    update_check,
    remove_token,
    get_ready_for_purge,
    token_cache
)
from filters import basic_filter, rugcheck_filter, holders_distribution_filter
from trader import attempt_buy_token, load_private_key
from telegram_alert import send_token_alert
import config

stats = {
    "start_time": time.time(),
    "token_count": 0,
    "last_token": None,
    "last_cleanup": None,
}


def on_token_received(token: dict):
    if not token or not token.get("mint"):
        return

    print(f"[WS] New token: {token['symbol']} ({token['mint']})")
    add_token_if_new(token["mint"], token)

    stats["token_count"] += 1
    stats["last_token"] = {
        "symbol": token.get("symbol", "?"),
        "mint": token.get("mint"),
        "timestamp": time.strftime("%H:%M:%S")
    }


def run_cleanup_loop():
    while True:
        time.sleep(config.CACHE_CLEANUP_INTERVAL_SECONDS)
        cleanup_expired_tokens()
        stats["last_cleanup"] = time.strftime("%H:%M:%S")


def run_recheck_loop():
    while True:
        time.sleep(300)  # every 5 minutes
        to_recheck = get_due_for_check(interval=300)
        print(f"[RECHECK] {len(to_recheck)} tokens due for check.")
        for entry in to_recheck:
            mint = entry["address"]
            data = entry["data"]
            try:
                simulated_token = type("Token", (), {})()
                simulated_token.name = data.get("name", "Unknown")
                simulated_token.symbol = data.get("symbol", "???")
                simulated_token.address = mint
                simulated_token.price_usd = 0.001
                simulated_token.liquidity_usd = float(data.get("solAmount", 0)) * config.SOL_PRICE_USD
                simulated_token.fdv = float(data.get("marketCapSol", 0)) * config.SOL_PRICE_USD
                simulated_token.pair_id = None
                simulated_token.source = "pumpfun"

                if all([
                    basic_filter(simulated_token),
                    rugcheck_filter(mint),
                    holders_distribution_filter(mint)
                ]):
                    print(f"[RECHECK ✅] Token {simulated_token.symbol} now qualifies!")
                    send_token_alert(simulated_token)
                    if config.AUTO_BUY_ENABLED:
                        attempt_buy_token(simulated_token)

                update_check(mint, signal_strength=1)
            except Exception as e:
                print(f"[ERROR] Token {mint} processing failed: {e}")

        # Purge old tokens
        for mint in get_ready_for_purge():
            print(f"[PURGE] Removing expired token: {mint}")
            remove_token(mint)


def run_stats_loop():
    while True:
        time.sleep(60)
        uptime = int(time.time() - stats["start_time"])
        h, rem = divmod(uptime, 3600)
        m, s = divmod(rem, 60)
        print("\n==============================")
        print("🧠 BOT STATUS REPORT")
        print(f"⏱  Uptime: {h:02}:{m:02}:{s:02}")
        print(f"📦  Tokens Seen: {stats['token_count']}")
        print(f"🧠  Current Cache Size: {len(token_cache)}")
        if stats["last_token"]:
            print(f"🆕  Last Token: {stats['last_token']['symbol']} at {stats['last_token']['timestamp']}")
        if stats["last_cleanup"]:
            print(f"🧹  Last Cleanup: {stats['last_cleanup']}")
        print("==============================\n")


def main():
    print("[INFO] Starting Solana Sniper Bot...")

    # Load wallet once at startup
    if config.AUTO_BUY_ENABLED:
        load_private_key()

    # Start WebSocket listener in background
    ws_listener = WebSocketListener(on_token_received)
    ws_thread = threading.Thread(target=ws_listener.run, name="WebSocketThread", daemon=True)
    ws_thread.start()

    # Start cleanup, recheck, and stats loops in parallel
    threading.Thread(target=run_cleanup_loop, name="CleanupThread", daemon=True).start()
    threading.Thread(target=run_recheck_loop, name="RecheckThread", daemon=True).start()
    threading.Thread(target=run_stats_loop, name="StatsThread", daemon=True).start()

    # Block main thread forever
    ws_thread.join()


if __name__ == "__main__":
    main()
