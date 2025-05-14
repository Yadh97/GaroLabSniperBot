# Filename: filters.py

import requests
from solders.pubkey import Pubkey
from solana.rpc.api import Client
import config

# Initialize Solana RPC client with correct commitment level
rpc_client = Client(config.RPC_HTTP_ENDPOINT, commitment=config.COMMITMENT)

def basic_filter(token) -> bool:
    """
    Basic token screen: filters by liquidity and market cap bounds.
    """
    if token.liquidity_usd < config.MIN_LIQUIDITY_USD:
        print(f"[FILTER ❌] {token.symbol}: Liquidity too low (${token.liquidity_usd})")
        return False
    if token.fdv <= 0 or token.fdv > config.MAX_FDV_USD:
        print(f"[FILTER ❌] {token.symbol}: FDV (${token.fdv}) out of range.")
        return False
    return True

def rugcheck_filter(token_address: str) -> bool:
    """
    Validate token safety using RugCheck. Reject if flagged as dangerous.
    """
    url = f"{config.RUGCHECK_BASE_URL}/{token_address}/report"
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code == 404:
            print(f"[INFO] RugCheck: Token not found: {token_address}")
            return False
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"[ERROR] RugCheck fetch failed: {e}")
        return False

    if data.get("rugged") is True:
        return False
    if str(data.get("result", "")).lower() in ("danger", "blacklisted"):
        return False
    if data.get("mintAuthority") not in (None, "", "null"):
        return False
    if data.get("freezeAuthority") not in (None, "", "null"):
        return False
    if data.get("knownAccounts"):
        return False

    return True

def holders_distribution_filter(token_address: str) -> bool:
    """
    Filters tokens where any of the top holders hold too much of total supply.
    """
    try:
        pubkey = Pubkey.from_string(token_address)

        # Fetch total supply
        supply_resp = rpc_client.get_token_supply(pubkey)
        total_amount = int(supply_resp.value.amount.amount)
        if total_amount == 0:
            print(f"[WARN] Token {token_address} has zero supply.")
            return False

        # Fetch top holders
        holders_resp = rpc_client.get_token_largest_accounts(pubkey)
        for idx, holder in enumerate(holders_resp.value[:10]):
            holder_amount = int(holder.amount.amount)
            share_percent = (holder_amount / total_amount) * 100
            if share_percent > config.TOP_HOLDER_MAX_PERCENT:
                print(f"[FILTER ❌] Token {token_address}: Holder #{idx+1} holds {share_percent:.2f}%. Too much.")
                return False

    except Exception as e:
        print(f"[ERROR] Holder check failed for {token_address}: {e}")
        return False

    return True
