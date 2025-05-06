import time
import config
import filters
import notifier
import data_sources
import trader

# Track already alerted tokens to avoid duplicates
seen_tokens = set()

def main():
    print("[INFO] Solana Sniper Bot started. Auto-buy is", "ON" if config.AUTO_BUY else "OFF")

    if trader.USER_KEYPAIR is None:
        trader.load_private_key()
        print(f"[INFO] Trading wallet loaded: {trader.USER_PUBKEY_STR}")

    while True:
        try:
            new_tokens = data_sources.get_new_tokens_combined()
            for token in new_tokens:
                if token.address in seen_tokens:
                    continue
                seen_tokens.add(token.address)

                # ✅ TEST MODE (force alert for first token)
                print(f"[TEST MODE] Alerting on token: {token.symbol} ({token.address})")
                notifier.notify_new_token(token)
                break  # Remove if you want to alert on multiple test tokens

                # 🔒 PRODUCTION FILTERS (uncomment after test)
                # if not filters.basic_filter(token):
                #     continue
                # if not filters.rugcheck_filter(token.address):
                #     continue
                # if not filters.holders_distribution_filter(token.address):
                #     continue

                # ✅ If passed filters, notify
                # notifier.notify_new_token(token)

                # Optional: Auto-buy logic
                # if config.AUTO_BUY:
                #     try:
                #         txid = trader.jupiter_swap(
                #             input_mint=config.SOL_MINT_ADDRESS,
                #             output_mint=token.address,
                #             amount=int(config.TRADE_SIZE_SOL * 1e9),
                #             slippage_bps=config.SLIPPAGE_BPS
                #         )
                #         notifier.notify_new_token(token, auto_buy=True, buy_txid=txid)
                #     except Exception as e:
                #         print(f"[ERROR] Auto-buy failed: {e}")

        except Exception as e:
            print(f"[ERROR] Main loop exception: {e}")

        time.sleep(config.POLL_INTERVAL)

if __name__ == "__main__":
    main()
