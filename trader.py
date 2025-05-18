# Filename: trader.py

import requests
from base58 import b58decode
from solders.keypair import Keypair as SoldersKeypair
from solders.transaction import VersionedTransaction
from solana.rpc.api import Client
from solana.rpc.types import TxOpts
from base64 import b64decode
import config

# Initialize HTTP RPC client
rpc_client = Client(config.RPC_HTTP_ENDPOINT)

# Wallet state
USER_KEYPAIR = None
USER_PUBKEY_STR = None


def load_private_key():
    """
    Load and decode user's private key from base58 string (stored in config).
    Supports both seed (32 bytes) and full (64 bytes) keys.
    """
    global USER_KEYPAIR, USER_PUBKEY_STR
    key_str = config.WALLET_PRIVATE_KEY.strip()

    if not key_str:
        raise ValueError("[KEY] WALLET_PRIVATE_KEY not set in config.")

    try:
        secret_bytes = b58decode(key_str)
        if len(secret_bytes) == 64:
            USER_KEYPAIR = SoldersKeypair.from_bytes(secret_bytes)
        elif len(secret_bytes) == 32:
            USER_KEYPAIR = SoldersKeypair.from_seed(secret_bytes)
        else:
            raise ValueError("Invalid private key length. Must be 32 or 64 bytes.")
        USER_PUBKEY_STR = str(USER_KEYPAIR.pubkey())
        print(f"[KEY ✅] Wallet loaded: {USER_PUBKEY_STR}")
    except Exception as e:
        raise RuntimeError(f"[KEY ERROR] Failed to load key: {e}")


def get_jupiter_swap_tx(input_mint, output_mint, amount_lamports, slippage_bps=100):
    """
    Query Jupiter Aggregator for swap route and prebuilt transaction.
    Returns a base64-encoded VersionedTransaction.
    """
    url = "https://quote-api.jup.ag/v6/swap"
    payload = {
        "inputMint": input_mint,
        "outputMint": output_mint,
        "amount": str(amount_lamports),
        "slippageBps": slippage_bps,
        "userPublicKey": USER_PUBKEY_STR,
        "wrapUnwrapSOL": True,
        "feeAccount": None,
        "asLegacyTransaction": False,
    }

    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        tx_base64 = response.json().get("swapTransaction")
        if not tx_base64:
            raise ValueError("Missing swapTransaction field in Jupiter response.")
        return tx_base64
    except Exception as e:
        print(f"[ERROR] Jupiter swap query failed: {e}")
        return None


def attempt_buy_token(token_info):
    """
    Perform a token purchase using Jupiter Aggregator with the loaded wallet.
    """
    global USER_KEYPAIR
    if USER_KEYPAIR is None:
        load_private_key()

    print(f"[BUY 🟡] Attempting buy: {token_info.symbol} ({token_info.address})")

    SOL_MINT = "So11111111111111111111111111111111111111112"
    amount_lamports = int(config.SWAP_AMOUNT_SOL * 1_000_000_000)

    swap_tx_base64 = get_jupiter_swap_tx(
        input_mint=SOL_MINT,
        output_mint=token_info.address,
        amount_lamports=amount_lamports,
        slippage_bps=config.SLIPPAGE_BPS
    )

    if not swap_tx_base64:
        print(f"[BUY ❌] Jupiter swap route unavailable for {token_info.symbol}")
        return

    try:
        raw_bytes = b64decode(swap_tx_base64)
        versioned_tx = VersionedTransaction.from_bytes(raw_bytes)
        signed_tx = versioned_tx.sign([USER_KEYPAIR])

        # Submit signed transaction
        result = rpc_client.send_transaction(signed_tx, opts=TxOpts(skip_confirmation=False))
        tx_sig = result.get("result")
        if tx_sig:
            print(f"[✅ BUY SUCCESS] {token_info.symbol} → https://solscan.io/tx/{tx_sig}")
        else:
            print(f"[ERROR] Transaction failed to broadcast: {result}")
    except Exception as e:
        print(f"[TX ERROR] Failed to sign/send {token_info.symbol}: {e}")
