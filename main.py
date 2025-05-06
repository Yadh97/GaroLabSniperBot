import asyncio
from websocket_listener import listen_new_tokens
from filters import basic_filter, rugcheck_filter, holders_distribution_filter
from notifier import notify_new_token
from trader import jupiter_swap, load_private_key
import config

seen_tokens = set()

async def handle_token(token_msg):
    mint = token_msg.get("mint")
    if not mint or mint in seen_tokens:
        return

    # Construct pseudo-token object for filters
    class Token:
        def __init__(self):
            self.address = mint
            self.name = token_msg.get("name", "Unknown")
            self.symbol = token_msg.get("symbol", "???")
            self.price_usd = 0.0  # real price not available from WS
            self.liquidity_usd = token_msg.get("solAmount", 0) * 100  # rough est. 1 SOL = $100
            self.fdv = token_msg.get("marketCapSol", 0) * 100
            self.pair_id = ""
            self.source = "pumpfun"
            self.decimals = None
            self.buzz_score = 0.0

    token = Token()

    if not basic_filter(token):
        return
    if not rugcheck_filter(token.address):
        return
    if not holders_distribution_filter(token.address):
        return

    seen_tokens.add(mint)
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

    notify_new_token(token, auto_buy=config.AUTO_BUY, buy_txid=buy_txid)

async def main():
    print("[INFO] Solana Sniper Bot started. WebSocket mode. Auto-buy is ON" if config.AUTO_BUY else "Auto-buy is OFF")
    load_private_key()

    async for token_msg in listen_new_tokens():
        if token_msg is None:
            continue
        await handle_token(token_msg)

if __name__ == "__main__":
    asyncio.run(main())
