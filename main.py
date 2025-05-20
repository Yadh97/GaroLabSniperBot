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
from simulated_trader import simulate_buy, get_simulated_pnl_report
import config

stats = {
    "start_time": time.time(),
    "token_count": 0,
    "last_token": None,
    "last_cleanup": None,
    "qualified": 0,
    "alerts_sent": 0,
}

def handle_new_token(token):
    mint = token.get("mint")
    if not mint:
        print("[WARN] Token has no mint address.")
        return

    print(f"[WS] New token from Pump.fun: {token['symbol']} ({mint})")
    add_token_if_new(mint, token)

    try:
        class TokenObj:
            def __init__(self, mint, symbol, data):
                self.address = mint
                self.symbol = symbol
                self.name = data.get("name")
                self.price_usd = 0.001
                self.liquidity_usd = data.get("solAmount", 0) * config.SOL_PRICE_USD
                self.fdv = data.get("marketCapSol", 0) * config.SOL_PRICE_USD
                self.pair_id = ""
                self.source = "pumpfun"

        token_obj = TokenObj(mint, token['symbol'], token)
        if all([
            basic_filter(token_obj),
            holders_distribution_filter(token_obj.address),
        ]):
            stats["qualified"] += 1
            print(f"[✅] Qualified Token: {token_obj.symbol} ({mint})")
            send_token_alert(token_obj)
            stats["alerts_sent"] += 1
            simulate_buy(token_obj)  # Simulated buy instead of real buy
            update_check(mint, signal_strength=1)
        else:
            update_check(mint, signal_strength=0)
    except Exception as e:
        print(f"[ERROR] Token {mint} processing failed: {e}")

    stats["token_count"] += 1
    stats["last_token"] = {
        "symbol": token.get("symbol"),
        "mint": mint,
        "timestamp": time.strftime("%H:%M:%S")
    }

async def recheck_tokens_loop():
    while True:
        due = get_due_for_check(interval=300)
        print(f"[RECHECK] {len(due)} tokens due for check.")
        for token in due:
            mint = token["address"]
            data = token["data"]
            try:
                class TokenObj:
                    def __init__(self, mint, symbol, data):
                        self.address = mint
                        self.symbol = data.get("symbol", "???")
                        self.name = data.get("name")
                        self.price_usd = 0.001
                        self.liquidity_usd = data.get("solAmount", 0) * config.SOL_PRICE_USD
                        self.fdv = data.get("marketCapSol", 0) * config.SOL_PRICE_USD
                        self.pair_id = ""
                        self.source = "pumpfun"

                token_obj = TokenObj(mint, data.get("symbol", "???"), data)
                if all([
                    basic_filter(token_obj),
                    holders_distribution_filter(token_obj.address),
                ]):
                    print(f"[RECHECK ✅] {token_obj.symbol} now qualifies!")
                    send_token_alert(token_obj)
                    stats["alerts_sent"] += 1
                    simulate_buy(token_obj)
                    update_check(mint, signal_strength=1)
                else:
                    update_check(mint, signal_strength=0)
            except Exception as e:
                print(f"[ERROR] Recheck failed for token {mint}: {e}")

        await asyncio.sleep(300)

async def cleanup_loop():
    while True:
        cleanup_expired_tokens()
        stats["last_cleanup"] = time.strftime("%H:%M:%S")
        await asyncio.sleep(config.CACHE_CLEANUP_INTERVAL_SECONDS)

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
        print(get_simulated_pnl_report())
        print("==============================\n")
        await asyncio.sleep(60)

def main():
    print("[INFO] Starting Solana Sniper Bot (Simulated Mode)...")

    ws_listener = WebSocketListener(on_token_callback=handle_new_token)
    ws_thread = threading.Thread(target=ws_listener.run, name="ws_listener", daemon=True)
    ws_thread.start()

    loop = asyncio.get_event_loop()
    loop.run_until_complete(asyncio.gather(
        recheck_tokens_loop(),
        cleanup_loop(),
        log_stats_loop(),
    ))

if __name__ == "__main__":
    main()
