# Filename: filters.py


from solders.pubkey import Pubkey
from solana.rpc.api import Client
import config
import requests

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
    try:
        pubkey = Pubkey.from_string(token_address)

        # Get total supply
        supply_resp = rpc_client.get_token_supply(pubkey)
        total_amount = int(supply_resp.value.amount)
        if total_amount == 0:
            print(f"[WARN] Token {token_address} has zero supply.")
            return False

        # Get largest holders
        holders_resp = rpc_client.get_token_largest_accounts(pubkey)
        holders = holders_resp.value
        if not holders:
            print(f"[WARN] Token {token_address} has no holder data.")
            return False

        for idx, holder in enumerate(holders[:10]):
            amount = int(holder.amount)
            if amount * 100 >= total_amount * config.TOP_HOLDER_MAX_PERCENT:
                print(f"[FILTER ❌] Token {token_address}: Holder #{idx+1} holds too much.")
                return False

    except Exception as e:
        print(f"[ERROR] Holder check failed for {token_address}: {e}")
        return False

    return True
