# filters.py

import requests
from solders.pubkey import Pubkey
from solana.rpc.api import Client
import config

# Initialize Solana RPC client
rpc_client = Client(config.RPC_URL)

def basic_filter(token) -> bool:
    """
    Basic filter: checks liquidity and market cap thresholds.
    Returns True if token meets minimum liquidity and maximum market cap criteria.
    """
    if token.liquidity_usd < config.MIN_LIQUIDITY_USD:
        return False
    if token.fdv <= 0 or token.fdv > config.MAX_FDV_USD:
        return False
    return True

def rugcheck_filter(token_address: str) -> bool:
    """
    RugCheck API validation:
    - No honeypot or blacklist
    - No active mint or freeze authorities
    Returns True if token passes these checks.
    """
    url = f"{config.RUGCHECK_BASE_URL}/{token_address}/report"
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code == 404:
            print(f"[INFO] RugCheck: Token not found: {token_address}")
            return False
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"[ERROR] RugCheck fetch failed: {e}")
        return False

    data = resp.json()
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
    Check top holders distribution:
    Ensures top 10 holders each hold less than X% of total supply.
    """
    try:
        pubkey = Pubkey.from_string(token_address)

        # 1. Get total token supply
        supply_resp = rpc_client.get_token_supply(pubkey)
        if not hasattr(supply_resp, "value"):
            print(f"[WARN] Token {token_address} has no supply data.")
            return False
        total_amount = int(supply_resp.value.amount or 0)
        if total_amount == 0:
            print(f"[WARN] Token {token_address} has zero supply.")
            return False

        # 2. Get top holders
        holders_resp = rpc_client.get_token_largest_accounts(pubkey)
        if not hasattr(holders_resp, "value") or not holders_resp.value:
            print(f"[WARN] Token {token_address} has no holders info.")
            return False

        for idx, holder in enumerate(holders_resp.value):
            if idx >= 10:
                break
            amount = int(holder.amount or 0)
            if amount * 100 >= total_amount * config.TOP_HOLDER_MAX_PERCENT:
                print(f"[FILTER ❌] Token {token_address}: Holder #{idx+1} holds too much.")
                return False

    except Exception as e:
        print(f"[ERROR] Holder check failed for {token_address}: {e}")
        return False

    return True

