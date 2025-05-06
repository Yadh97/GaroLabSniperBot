import requests
from dataclasses import dataclass
from typing import List
import os
import config
from models import TokenInfo
from dotenv import load_dotenv
load_dotenv()

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
    """Fetch newly created tokens from Pump.fun via Moralis API."""
    new_tokens: List[TokenInfo] = []

    moralis_key = os.getenv("MORALIS_API_KEY")
    if not moralis_key:
        print("[ERROR] MORALIS_API_KEY is missing or not loaded from environment.")
        return new_tokens

    url = f"{config.PUMPFUN_NEW_TOKENS_URL}?limit=50"
    headers = {
        "accept": "application/json",
        "X-API-Key": moralis_key
    }

    try:
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        results = data.get("result", [])
        for entry in results:
            try:
                token_addr = entry.get("tokenAddress")
                name = entry.get("name", "")
                symbol = entry.get("symbol", "")
                decimals = int(entry.get("decimals", "0") or 0)
                price_usd = float(entry.get("priceUsd", "0") or 0)
                liquidity = float(entry.get("liquidity", "0") or 0)
                fdv = float(entry.get("fullyDilutedValuation", "0") or 0)
                if not token_addr:
                    continue
                token = TokenInfo(
                    address=token_addr,
                    name=name,
                    symbol=symbol,
                    price_usd=price_usd,
                    liquidity_usd=liquidity,
                    fdv=fdv,
                    pair_id="",
                    source="pumpfun",
                    decimals=decimals
                )
                token.buzz_score = 0.0
                new_tokens.append(token)
            except Exception:
                continue
    except Exception as e:
        print(f"[ERROR] Pump.fun API failed: {e}")

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
