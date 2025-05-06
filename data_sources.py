import requests
from dataclasses import dataclass
from typing import List
import config

# --- Token Info Schema ---
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

def fetch_new_from_dexscreener() -> List[TokenInfo]:
    """Fetch new Solana tokens using DexScreener public API."""
    new_tokens: List[TokenInfo] = []
    url = "https://api.dexscreener.com/latest/pairs"

    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        pairs = data.get("pairs", [])
    except Exception as e:
        print(f"[ERROR] DexScreener API failed: {e}")
        return new_tokens

    for pair in pairs:
        try:
            if pair.get("chainId", "").lower() != "solana":
                continue

            base_token = pair.get("baseToken", {})
            price_usd = float(pair.get("priceUsd", "0") or 0)
            liquidity = float(pair.get("liquidity", "0") or 0)
            fdv = float(pair.get("fdv", "0") or 0)
            pair_id = pair.get("pairAddress", "")

            token_addr = base_token.get("address", "")
            symbol = base_token.get("symbol", "")
            name = base_token.get("name", "")
            decimals = int(base_token.get("decimals", "0") or 0)

            if not token_addr or not symbol or not name:
                continue

            token = TokenInfo(
                address=token_addr,
                name=name,
                symbol=symbol,
                price_usd=price_usd,
                liquidity_usd=liquidity,
                fdv=fdv,
                pair_id=pair_id,
                source="dexscreener",
                decimals=decimals,
                buzz_score=0.0
            )
            new_tokens.append(token)
        except Exception as e:
            print(f"[WARN] Skipped malformed pair: {e}")
            continue

    print(f"[INFO] Loaded {len(new_tokens)} Solana tokens from DexScreener.")
    return new_tokens

def fetch_new_from_pumpfun() -> List[TokenInfo]:
    """Fetch newly created tokens from Pump.fun via Moralis API."""
    new_tokens: List[TokenInfo] = []
    if not config.MORALIS_API_KEY:
        print("[WARN] Moralis API key not provided.")
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
        print(f"[ERROR] Pump.fun API failed: {e}")
        return new_tokens

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
            new_tokens.append(token)
        except Exception:
            continue

    return new_tokens

def get_new_tokens_combined() -> List[TokenInfo]:
    """Merge new tokens from DexScreener and Pump.fun."""
    tokens = []
    try:
        dex_tokens = fetch_new_from_dexscreener()
    except Exception as e:
        print(f"[ERROR] DexScreener error: {e}")
        dex_tokens = []

    try:
        pump_tokens = fetch_new_from_pumpfun()
    except Exception as e:
        print(f"[ERROR] Pump.fun error: {e}")
        pump_tokens = []

    seen = set()
    for t in dex_tokens + pump_tokens:
        if t.address not in seen:
            tokens.append(t)
            seen.add(t.address)

    return tokens
