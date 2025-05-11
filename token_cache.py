# Filename: filters.py

import requests
from solders.pubkey import Pubkey
from solana.rpc.api import Client
import config

# Setup RPC connection
rpc_client = Client(config.RPC_URL)

def basic_filter(token) -> bool:
    """
    Liquidity and FDV screening.
    ✅ Passes only if:
    - Liquidity > threshold
    - Market Cap (FDV) within safe bounds
    """
    if token.liquidity_usd < config.MIN_LIQUIDITY_USD:
        print(f"[FILTER ❌] {token.symbol}: Liquidity too low (${token.liquidity_usd})")
        return False
    if token.fdv <= 0 or token.fdv > config.MAX_FDV_USD:
        print(f"[FILTER ❌] {token.symbol}: Market Cap too high (${token.fdv})")
        return False
    return True

def rugcheck_filter(token_address: str) -> bool:
    """
    ✅ Token must:
    - Not be labeled dangerous/rugged
    - Have no active mint/freeze authorities
    - Not involve known malicious accounts
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
        print(f"[RUG ❌] Token {token_address} is flagged as rugged.")
        return False
    if str(data.get("result", "")).lower() in ("danger", "blacklisted"):
        print(f"[RUG ❌] Token {token_address} flagged as {data.get('result')}.")
        return False
    if data.get("mintAuthority") not in (None, "", "null"):
        print(f"[RUG ❌] Token {token_address} has active mint authority.")
        return False
    if data.get("freezeAuthority") not in (None, "", "null"):
        print(f"[RUG ❌] Token {token_address} has active freeze authority.")
        return False
    if data.get("knownAccounts"):
        print(f"[RUG ❌] Token {token_address} involves known malicious accounts.")
        return False

    return True

def holders_distribution_filter(token_address: str) -> bool:
    """
    ✅ Ensures none of the top 10 holders hold > X% of supply.
    """
    try:
        pubkey = Pubkey.from_string(token_address)

        # 1. Total supply
        supply_resp = rpc_client.get_token_supply(pubkey)
        supply_value = supply_resp.get("result", {}).get("value", {})
        total_amount_str = supply_value.get("amount")
        if total_amount_str is None:
            print(f"[HOLDERS ❌] Could not fetch supply for {token_address}")
            return False
        total_amount = int(total_amount_str)
        if total_amount == 0:
            print(f"[HOLDERS ❌] Token {token_address} has 0 supply.")
            return False

        # 2. Largest holders
        holders_resp = rpc_client.get_token_largest_accounts(pubkey)
        holders_info = holders_resp.get("result", {}).get("value", [])
        for idx, holder in enumerate(holders_info[:10]):
            holder_amount = int(holder.get("amount", 0))
            if holder_amount * 100 >= total_amount * config.TOP_HOLDER_MAX_PERCENT:
                print(f"[HOLDERS ❌] Top holder #{idx+1} owns >= {config.TOP_HOLDER_MAX_PERCENT}% of supply.")
                return False

    except Exception as e:
        print(f"[ERROR] Holder check failed for {token_address}: {e}")
        return False

    return True
