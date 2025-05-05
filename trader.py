import base58
import base64
import requests
from solders.keypair import Keypair as SoldersKeypair
from solders.transaction import VersionedTransaction
from solana.rpc.api import Client
from solana.rpc.types import TxOpts
from solana.publickey import PublicKey
import config

# Prepare Solana RPC client
rpc_client = Client(config.RPC_URL)

USER_KEYPAIR = None
USER_PUBKEY_STR = None

def load_private_key():
    """Load wallet private key from config into solders.Keypair."""
    global USER_KEYPAIR, USER_PUBKEY_STR
    key_str = config.PRIVATE_KEY.strip()
    if not key_str:
        raise Exception("No private key provided.")

    try:
        if key_str.startswith('['):
            import json
            nums = json.loads(key_str)
            secret_bytes = bytes(nums)
        else:
            secret_bytes = base58.b58decode(key_str)
    except Exception as e:
        raise Exception(f"Failed to decode PRIVATE_KEY: {e}")

    if len(secret_bytes) == 64:
        USER_KEYPAIR = SoldersKeypair.from_bytes(secret_bytes)
    elif len(secret_bytes) == 32:
        USER_KEYPAIR = SoldersKeypair.from_seed(secret_bytes)
    else:
        raise Exception("Invalid PRIVATE_KEY length. Must be 32 or 64 bytes.")

    USER_PUBKEY_STR = str(USER_KEYPAIR.pubkey())
    print(f"[INFO] Trading wallet loaded: {USER_PUBKEY_STR}")

def jupiter_swap(input_mint: str, output_mint: str, amount: int, slippage_bps: int) -> str:
    """
    Execute a swap on Jupiter Aggregator.
    Returns transaction signature if successful.
    """
    if USER_KEYPAIR is None:
        load_private_key()

    quote_url = "https://quote-api.jup.ag/v6/quote"
    swap_url = "https://quote-api.jup.ag/v6/swap"

    # 1. Get quote
    quote_params = {
        "inputMint": input_mint,
        "outputMint": output_mint,
        "amount": str(amount),
        "slippageBps": str(slippage_bps),
        "onlyDirectRoutes": False
    }
    quote_resp = requests.get(quote_url, params=quote_params, timeout=10)
    quote_resp.raise_for_status()
    quote_data = quote_resp.json()

    # 2. Get swap transaction
    swap_params = {
        "userPublicKey": USER_PUBKEY_STR,
        "wrapUnwrapSOL": True,
        "feeAccount": None,
        "quoteResponse": quote_data
    }
    swap_resp = requests.post(swap_url, json=swap_params, timeout=10)
    swap_resp.raise_for_status()
    swap_data = swap_resp.json()

    tx_base64 = swap_data.get("swapTransaction")
    if not tx_base64:
        raise Exception("Swap transaction data not found.")

    # 3. Decode, sign, and send
    tx_bytes = base64.b64decode(tx_base64)
    tx = VersionedTransaction.deserialize(tx_bytes)
    tx.sign([USER_KEYPAIR])

    send_resp = rpc_client.send_raw_transaction(tx.serialize(), opts=TxOpts(skip_confirmation=False))
    txid = send_resp.get("result")
    if not txid:
        raise Exception(f"Failed to send swap transaction: {send_resp}")
    return txid
