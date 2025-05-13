# Filename: trader.py

import requests
from base58 import b58decode
from solders.keypair import Keypair as SoldersKeypair
from solders.transaction import VersionedTransaction
from solana.rpc.api import Client
from solana.rpc.types import TxOpts
import config

# Initialize RPC client
rpc_client = Client(config.RPC_HTTP_ENDPOINT)

# User keypair and address
USER_KEYPAIR = None
USER_PUBKEY_STR = None

def load_private_key():
    """
    Loads the wallet private key from config and decodes into a Solana Keypair.
    """
    global USER_KEYPAIR, USER_PUBKEY_STR
    key_str = config.WALLET_PRIVATE_KEY.strip()

    if not key_str:
        raise Exception("[KEY] No private key provided.")
    
    try:
        secret_bytes = b58decode(key_str)
        if len(secret_bytes) == 64:
            USER_KEYPAIR = SoldersKeypair.from_bytes(secret_bytes)
        elif len(secret_bytes) == 32:
            USER_KEYPAIR = SoldersKeypair.from_seed(secret_bytes)
        else:
            raise Exception("Private key must be 32 or 64 bytes.")
        USER_PUBKEY_STR = str(USER_KEYPAIR.pubkey())
        print(f"[KEY] Wallet loaded: {USER_PUBKEY_STR}")
    except Exception as e:
        raise Exception(f"[KEY ERROR] Failed to decode wallet key: {e}")

def get_jupiter_swap_tx(input_mint, output_mint, amount, slippage_bps=100):
    """
    Requests a Jupiter route and pre-signed transaction for a swap.
    """
    url = "https://quote-api.jup.ag/v6/swap"
    headers = {"Content-Type": "application/json"}

    payload = {
        "inputMint": input_mint,
        "outputMint": output_mint,
        "amount": str(amount),
        "slippageBps": slippage_bps,
        "userPublicKey": USER_PUBKEY_STR,
        "wrapUnwrapSOL": True,
        "feeAccount": None,
        "asLegacyTransaction": False,
    }

    try:
        resp = requests.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        return data["swapTransaction"]  # base64-encoded tx
    except Exception as e:
        print(f"[ERROR] Jupiter swap failed: {e}")
        return None

def attempt_buy_token(token_info):
    """
    Initiates a swap via Jupiter Aggregator to purchase token using SOL.
    """
    global USER_KEYPAIR
    if USER_KEYPAIR is None:
        load_private_key()

    print(f"[BUYING] Attempting real buy for {token_info.symbol} ({token_info.address})")

    SOL_MINT = "So11111111111111111111111111111111111111112"
    amount_lamports = int(config.SWAP_AMOUNT_SOL * 1_000_000_000)  # Convert SOL to lamports

    jupiter_tx = get_jupiter_swap_tx(
        input_mint=SOL_MINT,
        output_mint=token_info.address,
        amount=amount_lamports,
        slippage_bps=config.SLIPPAGE_BPS
    )

    if not jupiter_tx:
        print(f"[BUY ❌] No swap transaction retrieved for {token_info.symbol}")
        return

    try:
        # Decode base64 transaction
        raw_tx = VersionedTransaction.from_bytes(
            bytes(requests.utils.unquote_to_bytes(jupiter_tx))
        )
        signed_tx = raw_tx.sign([USER_KEYPAIR])

        # Broadcast
        response = rpc_client.send_transaction(signed_tx, opts=TxOpts(skip_confirmation=False))
        tx_sig = response.get("result")
        if tx_sig:
            print(f"[✅ BUY SUCCESS] Transaction: https://solscan.io/tx/{tx_sig}")
        else:
            print(f"[ERROR] Transaction broadcast failed: {response}")
    except Exception as e:
        print(f"[TX ERROR] Failed to sign or send transaction: {e}")
