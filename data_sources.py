import requests
from dataclasses import dataclass
from typing import List
import config

# Data model for token info
@dataclass
class TokenInfo:
    address: str
    name: str
    symbol: str
    price_usd: float
    liquidity_usd: float
    fdv: float
    pair_id: str
    source: str
    decimals: int = None
    buzz_score: float = 0.0

def fetch_new_from_pumpfun() -> List[TokenInfo]:
    """Fetch newly created tokens from Pump.fun via Moralis."""
    new_tokens: List[TokenInfo] = []

    if not config.MORALIS_API_KEY:
        print("[WARN] MORALIS_API_KEY not set — skipping Pump.fun.")
        return new_tokens

    url = config.PUMPFUN_NEW_TOKENS_URL + "?limit=50"
    headers = {
        "accept": "application/json",
        "X-API-Key": config.MORALIS_API_KEY
    }

    try:
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        print(f"[ERROR] Pump.fun fetch failed: {e}")
        return new_tokens

    results = data.get("result", [])
    for entry in results:
        try:
            token_addr = entry.get("tokenAddress")
            name = entry.get("name") or "Unknown"
            symbol = entry.get("symbol") or "???"
            decimals = int(entry.get("decimals", 0) or 0)
            price_usd = float(entry.get("priceUsd", 0) or 0)
            liquidity = float(entry.get("liquidity", 0) or 0)
            fdv = float(entry.get("fullyDilutedValuation", 0) or 0)

            token = TokenInfo(
                address=token_addr,
                name=name,
                symbol=symbol,
                price_usd=price_usd,
                liquidity_usd=liquidity,
                fdv=fdv,
                pair_id="",  # Not available from Pump.fun directly
                source="pumpfun",
                decimals=decimals,
                buzz_score=0.0
            )
            new_tokens.append(token)
        except Exception as e:
            print(f"[WARN] Skipped token due to parse error: {e}")
            continue

    print(f"[INFO] Loaded {len(new_tokens)} new tokens from Pump.fun.")
    return new_tokens

def get_new_tokens_combined() -> List[TokenInfo]:
    """Fetch and return all tokens from all sources."""
    tokens = []
    try:
        pump_tokens = fetch_new_from_pumpfun()
        tokens.extend(pump_tokens)
    except Exception as e:
        print(f"[ERROR] Exception in fetch_new_from_pumpfun: {e}")

    # Add DexScreener logic later if they offer open feed
    return tokens
