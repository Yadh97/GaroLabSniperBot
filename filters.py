from solana.rpc.api import Client
from solana.publickey import PublicKey
import config
import requests

# Initialize a Solana RPC client (for holders and supply queries)
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
        # Note: RugCheck's public API allows ~5 requests/min without auth. If more needed, consider using an API key with authentication.
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"[ERROR] RugCheck API request failed for {token_address}: {e}")
        return False
    data = resp.json()
    # Check for active mint authority
    mint_auth = data.get("mintAuthority")
    if mint_auth not in (None, "", "null"):  # if mintAuthority is present and not null
        print(f"[INFO] Token {token_address} has an active mint authority: {mint_auth}")
        return False
    # Check for active freeze authority
    freeze_auth = data.get("freezeAuthority")
    if freeze_auth not in (None, "", "null"):
        print(f"[INFO] Token {token_address} has an active freeze authority: {freeze_auth}")
        return False
    # Check if RugCheck explicitly flagged it as honeypot or blacklist
    # If the token is not tradable or has blacklist, RugCheck might list a risk.
    risks = data.get("risks", [])
    for risk in risks:
        # risk could be an object with 'description' or 'name'
        desc = str(risk).lower()
        if "honeypot" in desc or "blacklist" in desc:
            print(f"[INFO] Token {token_address} flagged by RugCheck risk: {risk}")
            return False
    # Some RugCheck responses include 'rugged' or 'result' fields
    if data.get("rugged") is True:
        # 'rugged' = True would indicate liquidity is already pulled (token not safe to trade)
        return False
    result_label = str(data.get("result", "")).lower()
    if result_label in ("danger", "blacklisted"):
        # 'Danger' result implies high risk factors were found.
        # We allow 'Warning' or 'Safe' but not 'Danger' or explicit blacklist.
        # (Note: RugCheck might label Danger even for holder distribution issues that we handle separately. 
        # If needed, we could refine this to ignore Danger solely from holder concentration. For simplicity, skip any Danger.)
        return False
    # Check knownAccounts (if RugCheck identifies known scammer addresses involved)
    known_accounts = data.get("knownAccounts", [])
    if known_accounts:
        # If any known malicious account is associated (e.g., creator or top holder known for rugs)
        print(f"[INFO] Token {token_address} has known malicious accounts: {known_accounts}")
        return False
    # If none of the above high-risk flags are present, consider it passing RugCheck filter
    return True

def holders_distribution_filter(token_address: str) -> bool:
    """
    Check top holders distribution:
    Ensures top 10 holders each hold less than 5% of total supply.
    Returns True if condition is satisfied.
    """
    try:
        # Fetch token supply
        supply_resp = rpc_client.get_token_supply(PublicKey(token_address))
        supply_value = supply_resp.get("result", {}).get("value", {})
        total_amount_str = supply_value.get("amount")
        decimals = supply_value.get("decimals", 0)
        if total_amount_str is None:
            # If supply couldn't be fetched, return False (cannot verify)
            print(f"[WARN] Could not retrieve token supply for {token_address}")
            return False
        total_amount = int(total_amount_str)
        if total_amount == 0:
            return False
        # Fetch largest accounts (holders) for the token
        holders_resp = rpc_client.get_token_largest_accounts(PublicKey(token_address))
        holders_info = holders_resp.get("result", {}).get("value", [])
        # Check up to top 10 accounts
        for idx, holder in enumerate(holders_info):
            if idx >= 10:
                break
            amount_str = holder.get("amount")
            if amount_str is None:
                continue
            amount = int(amount_str)
            # Compare holder amount to total supply as a fraction
            # Check if holder > 5% of total: i.e., amount/total > 0.05 -> amount * 100 > total * 5
            # We'll use multiplication to avoid floating precision issues:
            if amount * 100 >= total_amount * config.TOP_HOLDER_MAX_PERCENT:
                # If any top holder has >= 5% (or >5%), fail
                return False
    except Exception as e:
        print(f"[ERROR] Exception in holders_distribution_filter for {token_address}: {e}")
        return False
    return True
