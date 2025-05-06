import time
import os
from data_sources import get_new_tokens_combined
from filters import basic_filter, rugcheck_filter, holders_distribution_filter
from notifier import notify_new_token
from trader import jupiter_swap, load_private_key
import config

seen_tokens = set()

def main():
    print("[INFO] Solana Sniper Bot started. Auto-buy is ON" if config.AUTO_BUY else "Auto-buy is OFF")

    load_private_key()

    while True:
        try:
            tokens = get_new_tokens_combined()

            for token in tokens:
                if token.address in seen_tokens:
                    continue

                # Step 1: Basic filter
                if not basic_filter(token):
                    continue

                # Step 2: Rugcheck
                if not rugcheck_filter(token.address):
                    continue

                # Step 3: Holders distribution
                if not holders_distribution_filter(token.address):
                    continue

                # Passed all filters
                seen_tokens.add(token.address)

                # Step 4: Optional auto-buy
                buy_txid = None
                if config.AUTO_BUY:
                    try:
                        amount = int(config.TRADE_SIZE_SOL * 1e9)  # lamports
                        buy_txid = jupiter_swap(
                            config.SOL_MINT_ADDRESS,
                            token.address,
                            amount,
                            config.SLIPPAGE_BPS
                        )
                        print(f"[BUY] Swap executed. TXID: {buy_txid}")
                    except Exception as e:
                        print(f"[ERROR] Buy failed: {e}")

                # Step 5: Notify
                notify_new_token(token, auto_buy=config.AUTO_BUY, buy_txid=buy_txid)

        except Exception as e:
            print(f"[ERROR] Main loop exception: {e}")

        time.sleep(config.POLL_INTERVAL)

if __name__ == "__main__":
    main()
