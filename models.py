# Filename: models.py

from dataclasses import dataclass
from typing import Optional

@dataclass
class TokenInfo:
    """
    TokenInfo represents metadata and liquidity data for a newly created token.
    This is the primary structured model used across filtering, alerting, and trading modules.
    """
    address: str                     # Token mint address
    name: str                        # Token name
    symbol: str                      # Token symbol (short name)
    price_usd: float                 # USD price (optional in some contexts)
    liquidity_usd: float             # Total liquidity in USD
    fdv: float                       # Fully Diluted Valuation (market cap)
    pair_id: Optional[str] = None    # Optional DexScreener pair ID or pool
    source: str = "unknown"          # Source of detection (e.g., 'pumpfun', 'dexscreener')
