import base58
import base64
import json
import requests
from solders.keypair import Keypair as SoldersKeypair
from solders.transaction import VersionedTransaction
from solana.rpc.api import Client
from solana.rpc.types import TxOpts
import config

# --- Solana RPC setup ---
rpc_client = Client(config.RPC_URL)

# --- Globals for wallet handling ---
USER_KEYPAIR = None
USER_PUBKEY_STR = None

def load_private_key():
    """Load the wallet private key into a solders.Keypair object."""
    global USER_KEYPAIR, USER_PUBKEY_STR
    key_str = config.PRIVATE_KEY.strip()
    if not key_str:
        raise Exception("Missing PRIVATE_KEY in environment.")

    try:
        # JSON array of ints (Anchor format)
        if key_str.startswith("["):
            nums = json.loads(key_str)
            secret_bytes = bytes(nums)
        else:
            # base58-encoded private key (64 or 32 bytes)
            secret_bytes = base58.b58decode(key_str)
    except Exception as e:
        raise Exception(f"Invalid PRIVATE_KEY format: {e}")

    if len(secret_bytes) == 64:
        USER_KEYPAIR = SoldersKeypair.from_bytes(secret_bytes)
    elif len(secret_bytes) == 32:
        USER_KEYPAIR = SoldersKeypair.from_seed(secret_bytes)
    else:
        raise Exception("PRIVATE_KEY must decode to 32 or 64 bytes.")

    USER_PUBKEY_STR = str(USER_KEYPAIR.pubkey())
    print(f"[INFO] Trading wallet loaded: {USER_PUBKEY_STR}")

def jupiter_swap(input_mint: str, output_mint: str, amount: int, slippage_bps: int) -> str:
    """
    Execute a token swap on Jupiter Aggregator.
    Returns the transaction ID (signature) on success.
    """
    if USER_KEYPAIR is None:
        load_private_key()

    quote_url = "https://quote-api.jup.ag/v6/quote"
    swap_url = "https://quote-api.jup.ag/v6/swap"

    # --- Step 1: Get quote ---
    params = {
        "inputMint": input_mint,
        "outputMint": output_mint,
        "amount": str(amount),
        "slippageBps": str(slippage_bps),
        "onlyDirectRoutes": False
    }
    try:
        quote_resp = requests.get(quote_url, params=params, timeout=10)
        quote_resp.raise_for_status()
        quote_data = quote_resp.json()
    except Exception as e:
        raise Exception(f"Failed to get Jupiter quote: {e}")

    # --- Step 2: Get swap transaction ---
    swap_params = {
        "userPublicKey": USER_PUBKEY_STR,
        "wrapUnwrapSOL": True,
        "feeAccount": None,
        "quoteResponse": quote_data
    }
    try:
        swap_resp = requests.post(swap_url, json=swap_params, timeout=10)
        swap_resp.raise_for_status()
        tx_data = swap_resp.json()
    except Exception as e:
        raise Exception(f"Failed to fetch swap tx: {e}")

    tx_b64 = tx_data.get("swapTransaction")
    if not tx_b64:
        raise Exception("Jupiter did not return swap transaction.")

    # --- Step 3: Decode, sign, and send tx ---
    try:
        tx_bytes = base64.b64decode(tx_b64)
        tx = VersionedTransaction.deserialize(tx_bytes)
        tx.sign([USER_KEYPAIR])
        send_resp = rpc_client.send_raw_transaction(tx.serialize(), opts=TxOpts(skip_confirmation=False))
        txid = send_resp.get("result")
        if not txid:
            raise Exception(f"Tx submission failed: {send_resp}")
        return txid
    except Exception as e:
        raise Exception(f"Transaction signing or send failed: {e}")
