from dataclasses import dataclass
from typing import List
import requests

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

def fetch_new_from_pumpfun_api() -> List[TokenInfo]:
    tokens: List[TokenInfo] = []
    url = "https://pump.fun/api/tokens"

    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        print(f"[ERROR] Pump.fun API fetch failed: {e}")
        return []

    for entry in data:
        try:
            token_addr = entry.get("id") or entry.get("mint")
            name = entry.get("name") or "Unknown"
            symbol = entry.get("symbol") or "???"
            decimals = int(entry.get("decimals", 0))
            price = float(entry.get("priceUsdc") or 0)
            liquidity = float(entry.get("liquidity") or 0)
            fdv = float(entry.get("fdv") or 0)

            if not token_addr:
                continue

            tokens.append(TokenInfo(
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
            ))
        except Exception:
            continue

    return tokens

def get_new_tokens_combined() -> List[TokenInfo]:
    final_tokens = []
    try:
        final_tokens.extend(fetch_new_from_pumpfun_api())
    except Exception as e:
        print(f"[ERROR] Failed loading Pump.fun tokens: {e}")
    return final_tokens
