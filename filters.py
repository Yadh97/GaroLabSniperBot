from solders.pubkey import Pubkey
from solana.rpc.api import Client
import requests
import config

# Solana RPC client for supply & holders
rpc_client = Client(config.RPC_URL)

def basic_filter(token) -> bool:
    """
    Liquidity and market cap check.
    ✅ Returns True if liquidity >= MIN and FDV <= MAX.
    """
    if token.liquidity_usd < config.MIN_LIQUIDITY_USD:
        print(f"[FILTER] REJECTED: {token.symbol} - Liquidity {token.liquidity_usd} < {config.MIN_LIQUIDITY_USD}")
        return False
    if token.fdv <= 0 or token.fdv > config.MAX_FDV_USD:
        print(f"[FILTER] REJECTED: {token.symbol} - FDV {token.fdv} > {config.MAX_FDV_USD}")
        return False
    return True

def rugcheck_filter(token_address: str) -> bool:
    """
    RugCheck filter:
    ✅ Reject if:
      - Active mint/freeze authorities
      - Honeypot/blacklist risk
      - Known malicious accounts
    """
    url = f"{config.RUGCHECK_BASE_URL}/{token_address}/report"
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"[ERROR] RugCheck fetch failed: {e}")
        return False

    data = resp.json()

    if data.get("mintAuthority"):
        print(f"[RUGCHECK] ❌ Active mint authority: {data.get('mintAuthority')}")
        return False
    if data.get("freezeAuthority"):
        print(f"[RUGCHECK] ❌ Active freeze authority: {data.get('freezeAuthority')}")
        return False
    if data.get("rugged") is True:
        print(f"[RUGCHECK] ❌ Token marked rugged.")
        return False

    result = data.get("result", "").lower()
    if result in ["danger", "blacklisted"]:
        print(f"[RUGCHECK] ❌ Risky token flagged: {result}")
        return False

    known_accounts = data.get("knownAccounts", [])
    if known_accounts:
        print(f"[RUGCHECK] ❌ Known malicious accounts: {known_accounts}")
        return False

    return True

def holders_distribution_filter(token_address: str) -> bool:
    """
    Holder filter:
    ✅ Pass if NO top 10 holder owns ≥ config.TOP_HOLDER_MAX_PERCENT %
    """
    try:
        supply_resp = rpc_client.get_token_supply(Pubkey.from_string(token_address))
        supply_info = supply_resp.get("result", {}).get("value", {})
        total = int(supply_info.get("amount", "0"))
        decimals = supply_info.get("decimals", 0)
        if total == 0:
            print(f"[HOLDERS] ❌ Zero supply: {token_address}")
            return False

        holders_resp = rpc_client.get_token_largest_accounts(Pubkey.from_string(token_address))
        holders = holders_resp.get("result", {}).get("value", [])

        for idx, h in enumerate(holders[:10]):
            amt = int(h.get("amount", "0"))
            if amt * 100 >= total * config.TOP_HOLDER_MAX_PERCENT:
                print(f"[HOLDERS] ❌ Holder {idx+1} owns >= {config.TOP_HOLDER_MAX_PERCENT}% of supply")
                return False
    except Exception as e:
        print(f"[ERROR] Holder check failed for {token_address}: {e}")
        return False

    return True
