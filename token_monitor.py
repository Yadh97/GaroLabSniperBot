# token_monitor.py

import asyncio
from filters import basic_filter, rugcheck_filter, holders_distribution_filter
from telegram_alert import send_token_alert
from trader import attempt_buy_token
from models import TokenInfo
from token_cache import token_cache, update_check, get_due_for_check, remove_token, get_ready_for_purge
import config
import time

def fetch_token_info_simulated(address: str) -> TokenInfo:
    # Simulate updated token info (replace with real data fetching if available)
    return TokenInfo(
        address=address,
        name="SimulatedToken",
        symbol="SIM",
        price_usd=0.001,
        liquidity_usd=25000,
        fdv=450000,
        pair_id="simulated123",
        source="pumpfun"
    )

async def recheck_tokens_loop():
    while True:
        due_tokens = get_due_for_check(interval=300)
        print(f"[RECHECK] {len(due_tokens)} tokens due for check.")
        for token_state in due_tokens:
            token_addr = token_state['data']['mint']
            token_info = fetch_token_info_simulated(token_addr)

            token = TokenInfo(
                address=token_info.address,
                name=token_info.name,
                symbol=token_info.symbol,
                price_usd=token_info.price_usd,
                liquidity_usd=token_info.liquidity_usd,
                fdv=token_info.fdv,
                pair_id=token_info.pair_id,
                source=token_info.source
            )

            if all([
                basic_filter(token),
                rugcheck_filter(token.address),
                holders_distribution_filter(token.address)
            ]):
                print(f"[✅] Token PASSED all filters: {token.symbol}")
                send_token_alert(token)
                if config.AUTO_BUY_ENABLED:
                    attempt_buy_token(token)

                update_check(token_addr, signal_strength=1)

        # Purge old inactive tokens
        to_remove = get_ready_for_purge()
        for mint in to_remove:
            print(f"[PURGE] Removing stale token: {mint}")
            remove_token(mint)

        await asyncio.sleep(300)
