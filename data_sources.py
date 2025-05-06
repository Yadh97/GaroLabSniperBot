import requests
from bs4 import BeautifulSoup
from dataclasses import dataclass
from typing import List
import config

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
    new_tokens: List[TokenInfo] = []
    try:
        resp = requests.get(config.DEXSCREENER_NEW_PAIRS_URL, timeout=10)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"[ERROR] Failed to fetch DexScreener new pairs: {e}")
        return new_tokens
    soup = BeautifulSoup(resp.text, "html.parser")
    anchors = soup.find_all('a')
    for a in anchors:
        href = a.get('href', '')
        text = a.get_text(separator=" ").strip()
        if href.startswith("/solana/") and " / SOL " in text:
            parts = text.split(" $ ")
            if len(parts) < 4:
                continue
            name_symbol_part = parts[0]
            liquidity_part = parts[-2]
            mcap_part = parts[-1]
            price_part = parts[1]
            if name_symbol_part.startswith("#"):
                try:
                    first_space = name_symbol_part.index(" ")
                    name_symbol_part = name_symbol_part[first_space+1:].strip()
                except ValueError:
                    name_symbol_part = name_symbol_part.lstrip("#").strip()
            if " / SOL " in name_symbol_part:
                symbol = name_symbol_part.split(" / SOL ")[0].strip()
                name = name_symbol_part.split(" / SOL ")[1].strip()
            else:
                continue
            try:
                price_usd = float(price_part.strip().split()[0])
            except ValueError:
                continue
            def parse_dollar_value(val_str: str) -> float:
                val_str = val_str.strip().replace("$", "")
                multiplier = 1.0
                if val_str.endswith("K"):
                    multiplier = 1000.0
                    val_str = val_str[:-1]
                elif val_str.endswith("M"):
                    multiplier = 1000000.0
                    val_str = val_str[:-1]
                try:
                    return float(val_str) * multiplier
                except ValueError:
                    return 0.0
            liquidity_usd = parse_dollar_value(liquidity_part)
            fdv = parse_dollar_value(mcap_part)
            pair_id = href.split("/")[2] if len(href.split("/")) >= 3 else ""
            token_addr = ""
            if pair_id:
                try:
                    api_url = f"https://api.dexscreener.com/latest/dex/pairs/solana/{pair_id}"
                    pair_data = requests.get(api_url, timeout=5).json()
                    if "pairs" in pair_data and pair_data["pairs"]:
                        pair_info = pair_data["pairs"][0]
                        base = pair_info.get("baseToken", {})
                        quote = pair_info.get("quoteToken", {})
                        base_addr = base.get("address", "")
                        quote_addr = quote.get("address", "")
                        base_symbol = base.get("symbol", "").upper()
                        quote_symbol = quote.get("symbol", "").upper()
                        if base_addr and (base_symbol == "SOL" or base_addr == config.SOL_MINT_ADDRESS):
                            token_addr = quote_addr
                        elif quote_addr and (quote_symbol == "SOL" or quote_addr == config.SOL_MINT_ADDRESS):
                            token_addr = base_addr
                        else:
                            continue
                    else:
                        continue
                except Exception as e:
                    print(f"[WARN] Could not fetch pair details for {symbol}: {e}")
                    continue
            if not token_addr:
                continue
            token = TokenInfo(
                address=token_addr,
                name=name,
                symbol=symbol,
                price_usd=price_usd,
                liquidity_usd=liquidity_usd,
                fdv=fdv,
                pair_id=pair_id,
                source="dexscreener"
            )
            token.buzz_score = 0.0
            new_tokens.append(token)
    return new_tokens

def fetch_new_from_pumpfun() -> List[TokenInfo]:
    new_tokens: List[TokenInfo] = []
    if not config.MORALIS_API_KEY:
        print("[WARN] Moralis API key not provided. Skipping Pump.fun data.")
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
        print(f"[ERROR] Failed to fetch Pump.fun new tokens: {e}")
        return new_tokens
    results = data.get("result", [])
    for entry in results:
        try:
            token_addr = entry.get("tokenAddress")
            name = entry.get("name", "")
            symbol = entry.get("symbol", "")
            decimals = int(entry.get("decimals", "0")) if entry.get("decimals") is not None else None
            price_usd = float(entry.get("priceUsd", "0") or 0)
            liquidity = float(entry.get("liquidity", "0") or 0)
            fdv = float(entry.get("fullyDilutedValuation", "0") or 0)
        except Exception as e:
            continue
        if not token_addr:
            continue
        pair_id = ""
        token = TokenInfo(
            address=token_addr,
            name=name,
            symbol=symbol,
            price_usd=price_usd,
            liquidity_usd=liquidity,
            fdv=fdv,
            pair_id=pair_id,
            source="pumpfun",
            decimals=decimals
        )
        token.buzz_score = 0.0
        new_tokens.append(token)
    return new_tokens

def get_new_tokens_combined() -> List[TokenInfo]:
    tokens = []
    try:
        dex_tokens = fetch_new_from_dexscreener()
    except Exception as e:
        dex_tokens = []
        print(f"[ERROR] Exception in fetch_new_from_dexscreener: {e}")
    try:
        pump_tokens = fetch_new_from_pumpfun()
    except Exception as e:
        pump_tokens = []
        print(f"[ERROR] Exception in fetch_new_from_pumpfun: {e}")
    seen_addresses = set()
    for t in dex_tokens + pump_tokens:
        if t.address in seen_addresses:
            continue
        seen_addresses.add(t.address)
        tokens.append(t)
    return tokens
