import requests
from bs4 import BeautifulSoup
from dataclasses import dataclass
from typing import List
import config

# Data class to represent a token's info
@dataclass
class TokenInfo:
    address: str        # SPL token mint address
    name: str           # Token name
    symbol: str         # Token symbol or ticker
    price_usd: float    # Current price in USD
    liquidity_usd: float  # Total liquidity in USD
    fdv: float          # Fully diluted valuation (market cap) in USD
    pair_id: str        # DEX pair ID (for DexScreener queries)
    source: str         # Source of discovery ('dexscreener' or 'pumpfun')
    decimals: int = None  # Token decimals (if known, optional)
    buzz_score: float = 0.0  # Placeholder for social buzz score (for future use)

def fetch_new_from_dexscreener() -> List[TokenInfo]:
    """Fetch newly launched token pairs from DexScreener (Solana only)."""
    new_tokens: List[TokenInfo] = []
    try:
        resp = requests.get(config.DEXSCREENER_NEW_PAIRS_URL, timeout=10)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"[ERROR] Failed to fetch DexScreener new pairs: {e}")
        return new_tokens
    # Parse the HTML content for Solana pairs
    soup = BeautifulSoup(resp.text, "html.parser")
    # Each pair is a link under the New Pairs page; find all link elements
    anchors = soup.find_all('a')
    for a in anchors:
        href = a.get('href', '')
        text = a.get_text(separator=" ").strip()
        # Filter only Solana pairs (URL starts with /solana/) and ensure text has " / SOL "
        if href.startswith("/solana/") and " / SOL " in text:
            # Example text format: "# 10 QOTUS / SOL QUANT OF THE UNITED STATES $ 0.001265 ... $ 122K $ 1.2M"
            # We will split the text by " $ " to extract key parts.
            parts = text.split(" $ ")
            if len(parts) < 4:
                continue  # if format unexpected, skip
            # parts[0] includes rank, symbol, base, name (e.g. "# 10 QOTUS / SOL QUANT OF THE UNITED STATES")
            # parts[1] is price (USD) as a string (e.g. "0.001265")
            # parts[2] contains a bunch of data including volume and percentage changes, which we don't need for now
            # parts[3] is liquidity (like "122K")
            # parts[4] is market cap (like "1.2M"), but because split with separator " $ ", the last part might combine liquidity and mcap with a trailing $ if present.
            # Actually after splitting by " $ ", parts should be:
            # [ "# 10 QOTUS / SOL QUANT OF THE UNITED STATES", "0.001265 4h 16m 76,446 46,992 $ 3.1M 77,844 -1.00% 1.76% 592% 592%", "122K", "1.2M" ]
            # In some cases the volume section might itself contain a "$", but DexScreener uses "$" primarily for USD values (price, liquidity, mcap).
            # We will try to identify liquidity and mcap by the last two parts.
            name_symbol_part = parts[0]
            liquidity_part = parts[-2]  # second last part
            mcap_part = parts[-1]       # last part
            price_part = parts[1]
            # Extract symbol and name from name_symbol_part
            # Format: "# rank SYMBOL / SOL NAME"
            # We can remove the leading "# rank"
            if name_symbol_part.startswith("#"):
                # Remove leading "# <rank>" portion
                try:
                    first_space = name_symbol_part.index(" ")
                    name_symbol_part = name_symbol_part[first_space+1:].strip()
                except ValueError:
                    name_symbol_part = name_symbol_part.lstrip("#").strip()
            # Now name_symbol_part should start with "SYMBOL / SOL NAME"
            if " / SOL " in name_symbol_part:
                symbol = name_symbol_part.split(" / SOL ")[0].strip()
                name = name_symbol_part.split(" / SOL ")[1].strip()
            else:
                # In case format is slightly different, skip this entry
                continue
            # Parse price (USD)
            try:
                price_usd = float(price_part.strip().split()[0])
            except ValueError:
                # If parsing fails, skip
                continue
            # Parse liquidity and market cap, which may include K or M suffix
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
            # Extract pair ID from href (href format: /solana/<pairId>)
            pair_id = href.split("/")[2] if len(href.split("/")) >= 3 else ""
            # Token address will be determined via DexScreener API call below, for now placeholder
            token_addr = ""
            # Call DexScreener API to get token address (baseToken and quoteToken)
            if pair_id:
                try:
                    api_url = f"https://api.dexscreener.com/latest/dex/pairs/solana/{pair_id}"
                    pair_data = requests.get(api_url, timeout=5).json()
                    # The API returns a JSON with "pairs": [ {...} ]
                    if "pairs" in pair_data and pair_data["pairs"]:
                        pair_info = pair_data["pairs"][0]
                        base = pair_info.get("baseToken", {})
                        quote = pair_info.get("quoteToken", {})
                        # Identify which token is the new token (not SOL)
                        base_addr = base.get("address", "")
                        quote_addr = quote.get("address", "")
                        base_symbol = base.get("symbol", "").upper()
                        quote_symbol = quote.get("symbol", "").upper()
                        # In Solana pairs, one side will be SOL (or wSOL). We check which side is not SOL.
                        if base_addr and (base_symbol == "SOL" or base_addr == config.SOL_MINT_ADDRESS):
                            token_addr = quote_addr
                        elif quote_addr and (quote_symbol == "SOL" or quote_addr == config.SOL_MINT_ADDRESS):
                            token_addr = base_addr
                        else:
                            # If neither side is SOL (less likely for Solana new pairs page), then skip
                            continue
                        # Also get decimals if provided (DexScreener might not provide decimals directly)
                        # We can infer decimals if FDV and price are given along with supply, but that's complex. We'll leave decimals None here.
                    else:
                        continue
                except Exception as e:
                    print(f"[WARN] Could not fetch pair details for {symbol}: {e}")
                    continue
            if not token_addr:
                # If we couldn't determine token address, skip this entry
                continue
            # Create TokenInfo object
            token = TokenInfo(
                address=token_addr,
                name=name,
                symbol=symbol,
                price_usd=price_usd,
                liquidity_usd=liquidity_usd,
                fdv=fdv,
                pair_id=pair_id,
                source="dexscreener",
            )
            # Placeholder for buzz score (could integrate social media sentiment in future)
            token.buzz_score = 0.0  # Future implementation can update this
            new_tokens.append(token)
    return new_tokens

def fetch_new_from_pumpfun() -> List[TokenInfo]:
    """Fetch newly created tokens from Pump.fun via Moralis API."""
    new_tokens: List[TokenInfo] = []
    if not config.MORALIS_API_KEY:
        # Moralis API key is required for Pump.fun data
        print("[WARN] Moralis API key not provided. Skipping Pump.fun data.")
        return new_tokens
    url = config.PUMPFUN_NEW_TOKENS_URL + "?limit=50"  # adjust limit as needed (50 new tokens)
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
    # The Moralis Pump.fun API returns a JSON with "result" as a list of token objects
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
            created_at = entry.get("createdAt", "")
            # We can optionally filter out tokens older than a certain time if needed.
        except Exception as e:
            # If any parsing fails, skip this entry
            continue
        if not token_addr:
            continue
        # DexScreener pair ID is not directly given by Moralis. We might find the pair on DexScreener later if needed.
        pair_id = ""  # unknown at this point
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
        token.buzz_score = 0.0  # Future: integrate Twitter/Telegram buzz analysis
        new_tokens.append(token)
    return new_tokens

def get_new_tokens_combined() -> List[TokenInfo]:
    """Fetch new tokens from both DexScreener and Pump.fun sources, merge results."""
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
    # Merge lists, avoiding duplicates by token address
    seen_addresses = set()
    for t in dex_tokens + pump_tokens:
        if t.address in seen_addresses:
            continue
        seen_addresses.add(t.address)
        tokens.append(t)
    # Optionally, we could sort by some priority (e.g., buzz_score or liquidity) if needed
    # tokens.sort(key=lambda x: x.buzz_score, reverse=True)  # Example: sort by buzz score (high to low)
    return tokens
# DexScreener and Pump.fun scraping logic
