# Filename: trader.py

from solana.rpc.api import Client
from solders.keypair import Keypair as SoldersKeypair
from solders.transaction import VersionedTransaction
from base58 import b58decode
import config

# Initialize Solana RPC client
rpc_client = Client(config.RPC_URL)

# Load and hold user keypair
USER_KEYPAIR = None
USER_PUBKEY_STR = None

def load_private_key():
    global USER_KEYPAIR, USER_PUBKEY_STR
    key_str = config.WALLET_PRIVATE_KEY.strip()
    if not key_str:
        raise Exception("No private key provided in config.")
    try:
        secret_bytes = b58decode(key_str)
        if len(secret_bytes) == 64:
            USER_KEYPAIR = SoldersKeypair.from_bytes(secret_bytes)
        elif len(secret_bytes) == 32:
            USER_KEYPAIR = SoldersKeypair.from_seed(secret_bytes)
        else:
            raise Exception("Invalid private key length.")
        USER_PUBKEY_STR = str(USER_KEYPAIR.pubkey())
        print(f"[INFO] Trading wallet loaded: {USER_PUBKEY_STR}")
    except Exception as e:
        raise Exception(f"[ERROR] Failed to decode wallet private key: {e}")

def attempt_buy_token(token_info):
    if USER_KEYPAIR is None:
        load_private_key()

    print(f"[BUY 🔁] Simulated purchase of token: {token_info.symbol} ({token_info.address})")
    # Real implementation would:
    # - Call Jupiter Aggregator for quote
    # - Create & sign swap transaction
    # - Broadcast via rpc_client.send_transaction(...)
    # For now, log the intent only
    # Future logic here

# Note: In a production implementation, you'd use Jupiter's REST endpoint to get a swap quote,
# construct a transaction with the route, sign with USER_KEYPAIR, and broadcast.
