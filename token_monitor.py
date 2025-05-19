# Filename: token_monitor.py

import asyncio
import time
from filters import basic_filter, rugcheck_filter, holders_distribution_filter
from telegram_alert import send_token_alert
from trader import attempt_buy_token
from simulated_trader import simulate_buy
from token_cache import (
    token_cache,
    update_check,
    get_due_for_check,
    remove_token,
    get_ready_for_purge,
    add_token_if_new,
)
from models import TokenInfo
import config
from queue import Queue

# Shared event queue (populated by websocket_listener)
event_queue: Queue = Queue()

def process_token_event(event: dict):
    """
    Processes a token event: applies filters, sends alert, simulates buy.
    """
    try:
        mint = event.get("mint")
        symbol = event.get("symbol", "???")
        liquidity = float(event.get("solAmount", 0)) * config.SOL_PRICE_USD
        mcap = float(event.get("marketCapSol", 0)) * config.SOL_PRICE_USD

        token_info = TokenInfo(
            address=mint,
            name=event.get("name", "Unknown"),
            symbol=symbol,
            price_usd=0.0,
            liquidity_usd=liquidity,
            fdv=mcap,
            pair_id="",
            source="pumpfun"
        )

        # === FILTERS ===
        if not basic_filter(token_info):
            print(f"[FILTER ❌] {symbol}: Basic filter failed.")
            return

        if not rugcheck_filter(token_info.address):
            print(f"[FILTER ❌] {symbol}: RugCheck failed.")
            return

        if not holders_distribution_filter(token_info.address):
            print(f"[FILTER ❌] {symbol}: Holder distribution failed.")
            return

        # === SUCCESS PATH ===
        print(f"[✅] {symbol} passed all filters! Triggering alert and (optional) buy.")
        send_token_alert(token_info)

        if config.AUTO_BUY_ENABLED:
            # attempt_buy_token(token_info)
            simulate_buy(token_info)
        update_check(mint, signal_strength=1)

    except Exception as e:
        print(f"[ERROR] Token {event.get('mint')} processing failed: {e}")


async def token_consumer_loop():
    """
    Continuously consumes token events from shared queue and applies filtering logic.
    """
    while True:
        try:
            if not event_queue.empty():
                event = event_queue.get()
                if event:
                    mint = event.get("mint")
                    add_token_if_new(mint, event)
                    process_token_event(event)
            else:
                await asyncio.sleep(0.2)
        except Exception as e:
            print(f"[ERROR] Consumer loop crashed: {e}")
            await asyncio.sleep(1)


async def recheck_tokens_loop():
    """
    Periodically re-evaluates cached tokens and purges expired entries.
    """
    while True:
        try:
            due_tokens = get_due_for_check(interval=300)
            print(f"[RECHECK] {len(due_tokens)} tokens due for check.")
            for entry in due_tokens:
                mint = entry["address"]
                event = entry["data"]
                try:
                    process_token_event(event)
                except Exception as e:
                    print(f"[RECHECK ERROR] Token {mint} recheck failed: {e}")

            # Purge expired
            expired = get_ready_for_purge()
            for mint in expired:
                print(f"[PURGE] Removing expired token: {mint}")
                remove_token(mint)

        except Exception as e:
            print(f"[ERROR] Recheck loop crashed: {e}")

        await asyncio.sleep(300)  # Repeat every 5 minutes
