from dataclasses import dataclass
from typing import List
import requests
import config

# --- Token Info Model ---

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

# --- Public Pump.fun API Integration ---

def fetch_new_from_pumpfun() -> List[TokenInfo]:
    new_tokens: List[TokenInfo] = []
    url = "https://client-api-2-0.pump.fun/token/hot"  # Public Pump.fun API (no key required)
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        tokens = response.json().get("tokens", [])
    except Exception as e:
        print(f"[ERROR] Pump.fun public API failed: {e}")
        return []

    for token in tokens:
        try:
            token_addr = token.get("id")
            name = token.get("name") or ""
            symbol = token.get("symbol") or ""
            decimals = token.get("decimals") or 0
            price = float(token.get("priceUsdc") or 0)
            liquidity = float(token.get("liquidity") or 0)
            fdv = float(token.get("fdv") or 0)

            if not token_addr:
                continue

            token_obj = TokenInfo(
                address=token_addr,
                name=name,
                symbol=symbol,
                price_usd=price,
                liquidity_usd=liquidity,
                fdv=fdv,
                pair_id="",
                source="pumpfun",
                decimals=decimals,
                buzz_score=0.0
            )
            new_tokens.append(token_obj)
        except Exception:
            continue

    return new_tokens

# --- Combined Sources Loader (only Pump.fun now) ---

def get_new_tokens_combined() -> List[TokenInfo]:
    tokens: List[TokenInfo] = []
    try:
        pump_tokens = fetch_new_from_pumpfun()
        tokens.extend(pump_tokens)
    except Exception as e:
        print(f"[ERROR] Exception in fetch_new_from_pumpfun: {e}")
    return tokens
