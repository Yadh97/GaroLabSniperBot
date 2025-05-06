from solders.pubkey import Pubkey
from solana.rpc.api import Client
import config
import requests

rpc_client = Client(config.RPC_URL)

def basic_filter(token) -> bool:
    if token.liquidity_usd < config.MIN_LIQUIDITY_USD:
        return False
    if token.fdv <= 0 or token.fdv > config.MAX_FDV_USD:
        return False
    return True

def rugcheck_filter(token_address: str) -> bool:
    url = f"{config.RUGCHECK_BASE_URL}/{token_address}/report"
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"[ERROR] RugCheck API request failed for {token_address}: {e}")
        return False
    data = resp.json()
    mint_auth = data.get("mintAuthority")
    if mint_auth not in (None, "", "null"):
        print(f"[INFO] Token {token_address} has an active mint authority: {mint_auth}")
        return False
    freeze_auth = data.get("freezeAuthority")
    if freeze_auth not in (None, "", "null"):
        print(f"[INFO] Token {token_address} has an active freeze authority: {freeze_auth}")
        return False
    risks = data.get("risks", [])
    for risk in risks:
        desc = str(risk).lower()
        if "honeypot" in desc or "blacklist" in desc:
            print(f"[INFO] Token {token_address} flagged by RugCheck risk: {risk}")
            return False
    if data.get("rugged") is True:
        return False
    result_label = str(data.get("result", "")).lower()
    if result_label in ("danger", "blacklisted"):
        return False
    known_accounts = data.get("knownAccounts", [])
    if known_accounts:
        print(f"[INFO] Token {token_address} has known malicious accounts: {known_accounts}")
        return False
    return True

def holders_distribution_filter(token_address: str) -> bool:
    try:
        supply_resp = rpc_client.get_token_supply(Pubkey.from_string(token_address))
        supply_value = supply_resp.get("result", {}).get("value", {})
        total_amount_str = supply_value.get("amount")
        decimals = supply_value.get("decimals", 0)
        if total_amount_str is None:
            print(f"[WARN] Could not retrieve token supply for {token_address}")
            return False
        total_amount = int(total_amount_str)
        if total_amount == 0:
            return False
        holders_resp = rpc_client.get_token_largest_accounts(Pubkey.from_string(token_address))
        holders_info = holders_resp.get("result", {}).get("value", [])
        for idx, holder in enumerate(holders_info):
            if idx >= 10:
                break
            amount_str = holder.get("amount")
            if amount_str is None:
                continue
            amount = int(amount_str)
            if amount * 100 >= total_amount * config.TOP_HOLDER_MAX_PERCENT:
                return False
    except Exception as e:
        print(f"[ERROR] Exception in holders_distribution_filter for {token_address}: {e}")
        return False
    return True
