
# Filename: token_monitor.py

import asyncio
import time
from filters import basic_filter, rugcheck_filter, holders_distribution_filter
from telegram_alert import send_token_alert
from trader import attempt_buy_token
from token_cache import (
    token_cache,
    get_due_for_check,
    update_check,
    get_ready_for_purge,
    remove_token
)
from models import TokenInfo
import config

async def recheck_tokens_loop():
    while True:
        due = get_due_for_check(interval=300)
        print(f"[RECHECK] {len(due)} tokens due for check.")
        for entry in due:
            addr = entry["address"]
            data = entry["data"]
            try:
                token_info = TokenInfo(
                    address=addr,
                    name=data.get("name", "Unknown"),
                    symbol=data.get("symbol", "?"),
                    price_usd=float(data.get("priceUsd", 0)),
                    liquidity_usd=float(data.get("solAmount", 0)) * config.SOL_PRICE_USD,
                    fdv=float(data.get("marketCapSol", 0)) * config.SOL_PRICE_USD,
                    pair_id=data.get("mint", ""),
                    source="pumpfun"
                )

                if all([
                    basic_filter(token_info),
                    rugcheck_filter(token_info.address),
                    holders_distribution_filter(token_info.address)
                ]):
                    print(f"[✅] {token_info.symbol} passed all filters.")
                    send_token_alert(token_info)
                    if config.AUTO_BUY_ENABLED:
                        attempt_buy_token(token_info)
                    update_check(addr, signal_strength=1)
                else:
                    update_check(addr, signal_strength=0)

            except Exception as e:
                print(f"[ERROR] Token {addr} processing failed: {e}")
                update_check(addr, signal_strength=0)

        # Remove old/inactive tokens
        purge = get_ready_for_purge()
        for mint in purge:
            print(f"[CACHE 🗑️] Removing inactive token {mint}")
            remove_token(mint)

        await asyncio.sleep(300)
