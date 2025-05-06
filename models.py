

from dataclasses import dataclass
from typing import Optional

@dataclass
class TokenInfo:
    address: str             # SPL token mint address
    name: str                # Token name
    symbol: str              # Token symbol or ticker
    price_usd: float         # Current price in USD
    liquidity_usd: float     # Liquidity in USD
    fdv: float               # Fully Diluted Valuation in USD
    pair_id: str             # DEX pair ID if applicable
    source: str              # Source (e.g., "dexscreener", "pumpfun")
    decimals: Optional[int] = None
    buzz_score: float = 0.0  # Optional future use (influencer buzz metric)
