import base58
import base64
from solders.keypair import Keypair as SoldersKeypair
from solders.transaction import VersionedTransaction
from solana.rpc.api import Client
from solana.rpc.types import TxOpts
import config

# Prepare Solana RPC client for sending transactions
rpc_client = Client(config.RPC_URL)

# Load the user's private key into a Keypair for signing
USER_KEYPAIR = None  # solders Keypair for signing transactions
USER_PUBKEY_STR = None  # public key in base58 string form

def load_private_key():
    """Load the wallet private key from config into a solders.Keypair."""
    global USER_KEYPAIR, USER_PUBKEY_STR
    key_str = config.WALLET_PRIVATE_KEY.strip()
    if not key_str:
        raise Exception("No private key provided for trading wallet.")
    try:
        if key_str.startswith('['):
            # Interpret as JSON array of ints
            import json
            nums = json.loads(key_str)
            secret_bytes = bytes(nums)
        else:
            # Assume base58 encoded key
            secret_bytes = base58.b58decode(key_str)
    except Exception as e:
        raise Exception(f"Failed to decode PRIVATE_KEY: {e}")
    # If we got 64 bytes, use directly; if 32 bytes, treat as seed
    if len(secret_bytes) == 64:
        USER_KEYPAIR = SoldersKeypair.from_bytes(secret_bytes)
    elif len(secret_bytes) == 32:
        USER_KEYPAIR = SoldersKeypair.from_seed(secret_bytes)
    else:
        raise Exception("PRIVATE_KEY length is invalid. Must be 32 (seed) or 64 (64-byte secret).")
    USER_PUBKEY_STR = str(USER_KEYPAIR.pubkey())
    # Sanity check: ensure key loaded
    print(f"[INFO] Trading wallet public key: {USER_PUBKEY_STR}")

def jupiter_swap(input_mint: str, output_mint: str, amount: int, slippage_bps: int) -> str:
    """
    Execute a swap on Jupiter aggregator.
    Returns the transaction signature (txid) if successful, or raises exception on failure.
    - input_mint/output_mint: token mint addresses (use config.SOL_MINT_ADDRESS for SOL).
    - amount: amount to swap in smallest units of input token.
    - slippage_bps: slippage in basis points.
    """
    if USER_KEYPAIR is None:
        load_private_key()
    # 1. Get quote for the swap
    quote_params = {
        "inputMint": input_mint,
        "outputMint": output_mint,
        "amount": str(amount),
        "slippageBps": str(slippage_bps)
    }
    try:
        quote_resp = requests.get(config.TRAILING

### main.py
```python
import time
import requests
from solana.publickey import PublicKey

import config
import data_sources
import filters
import notifier
import trader

def main():
    print(f"[INFO] Solana Sniper Bot started. Auto-buy is {'ON' if config.AUTO_BUY else 'OFF'}")
    seen_tokens = set()
    active_positions = []  # List of active positions for auto-sell monitoring

    # Pre-load trading keypair if auto-buy is enabled
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
        # Process new tokens
        for token in new_tokens:
            if token.address in seen_tokens:
                continue  # already processed
            seen_tokens.add(token.address)
            # Apply filtering criteria
            if not filters.basic_filter(token):
                continue
            if not filters.rugcheck_filter(token.address):
                continue
            if not filters.holders_distribution_filter(token.address):
                continue
            # Token passed all filters
            buy_txid = None
            if config.AUTO_BUY:
                try:
                    lamports = int(config.TRADE_SIZE_SOL * 1_000_000_000)  # convert SOL to lamports
                    txid = trader.jupiter_swap(config.SOL_MINT_ADDRESS, token.address, lamports, config.SLIPPAGE_BPS)
                    buy_txid = txid
                    print(f"[INFO] Auto-buy executed for {token.symbol}, transaction: {txid}")
                except Exception as e:
                    print(f"[ERROR] Auto-buy failed for {token.symbol}: {e}")
            # Send Telegram alert
            notifier.notify_new_token(token, auto_buy=config.AUTO_BUY, buy_txid=buy_txid)
            # If we auto-bought successfully, set up take-profit monitoring
            if config.AUTO_BUY and buy_txid:
                target_price_usd = token.price_usd * config.TAKE_PROFIT_MULTIPLE
                position = {
                    "address": token.address,
                    "symbol": token.symbol,
                    "target_price_usd": target_price_usd,
                    "pair_id": token.pair_id
                }
                # If pair_id is missing (e.g., from pump.fun source), attempt to find it via DexScreener token API
                if not position["pair_id"]:
                    try:
                        resp = requests.get(f"https://api.dexscreener.com/latest/dex/tokens/{token.address}", timeout=5)
                        if resp.status_code == 200:
                            info = resp.json()
                            if "pairs" in info and info["pairs"]:
                                for p in info["pairs"]:
                                    base_sym = p.get("baseToken", {}).get("symbol", "").upper()
                                    quote_sym = p.get("quoteToken", {}).get("symbol", "").upper()
                                    if base_sym == "SOL" or quote_sym == "SOL":
                                        position["pair_id"] = p.get("pairAddress", "")
                                        break
                                if not position["pair_id"]:
                                    position["pair_id"] = info["pairs"][0].get("pairAddress", "")
                    except Exception as e:
                        print(f"[WARN] Could not find pair ID for {token.symbol}: {e}")
                active_positions.append(position)

        # Check active positions for take-profit triggers
        for pos in active_positions[:]:
            try:
                current_price_usd = 0.0
                if pos.get("pair_id"):
                    # Fetch latest price from DexScreener for this pair
                    pair_resp = requests.get(f"https://api.dexscreener.com/latest/dex/pairs/solana/{pos['pair_id']}", timeout=5)
                    if pair_resp.status_code == 200:
                        pair_data = pair_resp.json()
                        if "pairs" in pair_data and pair_data["pairs"]:
                            # Take the first pair's data
                            price_usd_str = pair_data["pairs"][0].get("priceUsd")
                            if price_usd_str:
                                current_price_usd = float(price_usd_str)
                # (If pair_id is not available, we could use an alternative source or skip checking)
                if current_price_usd >= pos["target_price_usd"] and current_price_usd > 0:
                    print(f"[INFO] Take-profit target reached for {pos['symbol']}: current ${current_price_usd:.6f}, target ${pos['target_price_usd']:.6f}")
                    # Fetch wallet's token balance for this token
                    try:
                        accounts_resp = trader.rpc_client.get_token_accounts_by_owner(PublicKey(trader.USER_PUBKEY_STR), mint=PublicKey(pos["address"]))
                        accounts = accounts_resp.get("result", {}).get("value", [])
                    except Exception as e:
                        accounts = []
                        print(f"[WARN] Could not fetch token account for {pos['symbol']}: {e}")
                    if accounts:
                        token_amount_info = accounts[0]["account"]["data"]["parsed"]["info"]["tokenAmount"]
                        amount_raw = int(token_amount_info["amount"])  # amount in base units (no decimals)
                        if amount_raw > 0:
                            try:
                                sell_txid = trader.jupiter_swap(pos["address"], config.SOL_MINT_ADDRESS, amount_raw, config.SLIPPAGE_BPS)
                                print(f"[INFO] Auto-sell executed for {pos['symbol']}, transaction: {sell_txid}")
                                # Notify about the sell
                                solscan_link = f"https://solscan.io/tx/{sell_txid}"
                                sell_message = f"✅ Take-profit hit for *{pos['symbol']}*! Sold at ~{config.TAKE_PROFIT_MULTIPLE}x. [View Tx]({solscan_link})"
                                notifier.send_telegram_message(sell_message)
                            except Exception as e:
                                print(f"[ERROR] Auto-sell failed for {pos['symbol']}: {e}")
                        else:
                            print(f"[WARN] Token balance for {pos['symbol']} is zero or not found.")
                    else:
                        print(f"[WARN] No token account found for {pos['symbol']} in wallet; skipping sell.")
                    # Remove position from active tracking after attempting sell (to prevent repeat triggers)
                    active_positions.remove(pos)
            except Exception as e:
                print(f"[ERROR] Error while checking take-profit for {pos['symbol']}: {e}")
        time.sleep(config.POLL_INTERVAL)

if __name__ == "__main__":
    main()
