# Filename: filters.py

import requests
from solders.pubkey import Pubkey
from solana.rpc.api import Client
from config import load_config
import json
from loguru import logger

# Load config dict
config = load_config()

# Use the configured RPC with chosen commitment level
rpc_client = Client(config["RPC_HTTP_ENDPOINT"], commitment=config.get("COMMITMENT", "confirmed"))

class TokenFilter:
    def __init__(self):
        self.filter_stats = {
            "liquidity": 0,
            "fdv": 0,
            "rugcheck": 0,
            "holders": 0
        }

    def apply_filters(self, token: dict) -> bool:
        token_address = (token.get("mint") or token.get("address") or "").strip()
        
        if not token_address or len(token_address) < 32:
            logger.error(f"[FILTER ❌] Invalid token address (length={len(token_address)}): {token_address}")
            logger.error(json.dumps(token, indent=2))
            return False

        passed = True

        if not self.basic_filter(token):
            self.filter_stats["liquidity"] += 1
            passed = False

        if not self.fdv_filter(token):
            self.filter_stats["fdv"] += 1
            passed = False

        if not rugcheck_filter(token_address):
            self.filter_stats["rugcheck"] += 1
            passed = False

        if not holders_distribution_filter(token_address):
            self.filter_stats["holders"] += 1
            passed = False

        return passed

    def basic_filter(self, token) -> bool:
        if token["liquidity_usd"] < config["MIN_LIQUIDITY_USD"]:
            logger.warning(f"[FILTER ❌] {token.get('symbol', '?')}: Liquidity too low (${token['liquidity_usd']:,.2f})")
            return False
        return True

    def fdv_filter(self, token) -> bool:
        if token["fdv"] <= 0 or token["fdv"] > config["MAX_FDV_USD"]:
            logger.warning(f"[FILTER ❌] {token.get('symbol', '?')}: FDV (${token['fdv']:,.2f}) out of range.")
            return False
        return True

    def get_filter_statistics(self):
        return self.filter_stats

    def reset_filter_statistics(self):
        for key in self.filter_stats:
            self.filter_stats[key] = 0

def rugcheck_filter(token_address: str) -> bool:
    url = f"{config.get('RUGCHECK_BASE_URL', 'https://api.rugcheck.xyz/v1/tokens')}/{token_address}/report"
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code == 404:
            logger.info(f"[INFO] RugCheck: Token not found: {token_address}")
            return False
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        logger.error(f"[ERROR] RugCheck fetch failed: {e}")
        return False

    if data.get("rugged") is True:
        logger.warning(f"[FILTER ❌] {token_address}: Rugged token.")
        return False
    if str(data.get("result", "")).lower() in ("danger", "blacklisted"):
        logger.warning(f"[FILTER ❌] {token_address}: RugCheck marked dangerous/blacklisted.")
        return False
    if data.get("mintAuthority") not in (None, "", "null"):
        logger.warning(f"[FILTER ❌] {token_address}: Mint authority detected.")
        return False
    if data.get("freezeAuthority") not in (None, "", "null"):
        logger.warning(f"[FILTER ❌] {token_address}: Freeze authority detected.")
        return False
    if data.get("knownAccounts"):
        logger.warning(f"[FILTER ❌] {token_address}: Involves known accounts.")
        return False

    return True

def holders_distribution_filter(token_address: str) -> bool:
    try:
        if token_address.endswith("pump"):
            token_address = token_address[:-4]
        
        pubkey = Pubkey.from_string(token_address)

        supply_resp = rpc_client.get_token_supply(pubkey)
        if not hasattr(supply_resp, 'value'):
            logger.error(f"[ERROR] Supply response invalid for {token_address}: {supply_resp}")
            return False

        total_amount = int(supply_resp.value.amount)
        if total_amount == 0:
            logger.warning(f"[WARN] Token {token_address} has zero supply.")
            return False
        if pubkey.endswith("pump"):
            pubkey = pubkey[:-4]
        holders_resp = rpc_client.get_token_largest_accounts(pubkey)
        if not hasattr(holders_resp, 'value'):
            logger.error(f"[ERROR] Holder response invalid for {token_address}: {holders_resp}")
            return False

        holders = holders_resp.value[:10] if holders_resp.value else []

        for idx, holder in enumerate(holders):
            try:
                holder_amount = int(holder.amount.amount)
                if holder_amount * 100 >= total_amount * config["TOP_HOLDER_MAX_PERCENT"]:
                    logger.warning(f"[FILTER ❌] {token_address}: Holder #{idx+1} holds too much.")
                    return False
            except Exception as parse_err:
                logger.warning(f"[WARN] Failed to parse holder #{idx+1}: {parse_err}")

    except Exception as e:
        logger.error(f"[ERROR] Holder check failed for {token_address}: {e}")
        return False

    return True
