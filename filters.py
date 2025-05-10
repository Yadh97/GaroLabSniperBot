# filters.py

import requests
from solana.publickey import PublicKey
from solana.rpc.api import Client
import config

# Initialize a Solana RPC client
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
    Ensures top 10 holders each hold less than 5% of total supply.
    """
    try:
        # ✅ Updated to handle solana-py object response
        supply_resp = rpc_client.get_token_supply(PublicKey(token_address))
        supply_value = supply_resp.value
        total_amount = int(supply_value.amount)
        if total_amount == 0:
            return False

        holders_resp = rpc_client.get_token_largest_accounts(PublicKey(token_address))
        holders_info = holders_resp.value

        for idx, holder in enumerate(holders_info):
            if idx >= 10:
                break
            amount = int(holder.amount)
            if amount * 100 >= total_amount * config.TOP_HOLDER_MAX_PERCENT:
                return False
    except Exception as e:
        print(f"[ERROR] Holder check failed for {token_address}: {e}")
        return False
    return True
