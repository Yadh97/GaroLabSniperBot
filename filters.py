# Filename: filters.py

import requests
from solders.pubkey import Pubkey
from solana.rpc.api import Client
from config import load_config

# Load config dict
config = load_config()

# Use the configured RPC with chosen commitment level
rpc_client = Client(config["RPC_HTTP_ENDPOINT"], commitment=config.get("COMMITMENT", "confirmed"))

def basic_filter(token) -> bool:
    if token.liquidity_usd < config["MIN_LIQUIDITY_USD"]:
        print(f"[FILTER ❌] {token.symbol}: Liquidity too low (${token.liquidity_usd:,.2f})")
        return False
    if token.fdv <= 0 or token.fdv > config["MAX_FDV_USD"]:
        print(f"[FILTER ❌] {token.symbol}: FDV (${token.fdv:,.2f}) out of range.")
        return False
    return True

def rugcheck_filter(token_address: str) -> bool:
    url = f"{config.get('RUGCHECK_BASE_URL', 'https://api.rugcheck.xyz/tokens')}/{token_address}/report"
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
        print(f"[FILTER ❌] {token_address}: Rugged token.")
        return False
    if str(data.get("result", "")).lower() in ("danger", "blacklisted"):
        print(f"[FILTER ❌] {token_address}: RugCheck marked dangerous/blacklisted.")
        return False
    if data.get("mintAuthority") not in (None, "", "null"):
        print(f"[FILTER ❌] {token_address}: Mint authority detected.")
        return False
    if data.get("freezeAuthority") not in (None, "", "null"):
        print(f"[FILTER ❌] {token_address}: Freeze authority detected.")
        return False
    if data.get("knownAccounts"):
        print(f"[FILTER ❌] {token_address}: Involves known accounts.")
        return False

    return True

def holders_distribution_filter(token_address: str) -> bool:
    try:
        pubkey = Pubkey.from_string(token_address)
        supply_resp = rpc_client.get_token_supply(pubkey)
        total_amount = int(supply_resp.value.amount)
        if total_amount == 0:
            print(f"[WARN] Token {token_address} has zero supply.")
            return False

        holders_resp = rpc_client.get_token_largest_accounts(pubkey)
        holders = holders_resp.value[:10] if holders_resp.value else []

        for idx, holder in enumerate(holders):
            try:
                holder_amount = int(holder.amount.amount)
                if holder_amount * 100 >= total_amount * config["TOP_HOLDER_MAX_PERCENT"]:
                    print(f"[FILTER ❌] {token_address}: Holder #{idx+1} holds too much.")
                    return False
            except Exception as parse_err:
                print(f"[WARN] Failed to parse holder #{idx+1}: {parse_err}")

    except Exception as e:
        print(f"[ERROR] Holder check failed for {token_address}: {e}")
        return False

    return True
