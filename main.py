import time
import config
import data_sources
import filters
import notifier
import trader

def main():
    print(f"[INFO] Solana Sniper Bot started. Auto-buy is {'ON' if config.AUTO_BUY else 'OFF'}")
    seen_tokens = set()
    active_positions = []

    if config.AUTO_BUY:
        try:
            trader.load_private_key()
        except Exception as e:
            print(f"[ERROR] Failed to load trading private key: {e}")
            return

    while True:
        try:
            new_tokens = data_sources.get_new_tokens_combined()
        except Exception as e:
            print(f"[ERROR] Failed to fetch new tokens: {e}")
            new_tokens = []

        for token in new_tokens:
            if token.address in seen_tokens:
                continue
            seen_tokens.add(token.address)

            if not filters.basic_filter(token):
                continue
            if not filters.rugcheck_filter(token.address):
                continue
            if not filters.holders_distribution_filter(token.address):
                continue

            buy_txid = None
            if config.AUTO_BUY:
                try:
                    lamports = int(config.TRADE_SIZE_SOL * 1_000_000_000)
                    txid = trader.jupiter_swap(config.SOL_MINT_ADDRESS, token.address, lamports, config.SLIPPAGE_BPS)
                    buy_txid = txid
                    print(f"[INFO] Auto-buy executed for {token.symbol}, transaction: {txid}")
                except Exception as e:
                    print(f"[ERROR] Auto-buy failed for {token.symbol}: {e}")

            notifier.notify_new_token(token, auto_buy=config.AUTO_BUY, buy_txid=buy_txid)

            if config.AUTO_BUY and buy_txid:
                target_price_usd = token.price_usd * config.TAKE_PROFIT_MULTIPLE
                position = {
                    "address": token.address,
                    "symbol": token.symbol,
                    "target_price_usd": target_price_usd,
                    "pair_id": token.pair_id
                }
                active_positions.append(position)

        time.sleep(config.POLL_INTERVAL)

if __name__ == "__main__":
    main()
