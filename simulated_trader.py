# Filename: simulated_trader.py

import time
from typing import List, Dict
from models import TokenInfo

# In-memory ledger of simulated trades
simulated_ledger: List[Dict] = []

def simulate_buy(token_info: TokenInfo):
    """
    Records a simulated buy event with price and timestamp.
    """
    simulated_ledger.append({
        "address": token_info.address,
        "symbol": token_info.symbol,
        "name": token_info.name,
        "buy_price": token_info.price_usd,
        "buy_time": time.time(),
        "liquidity_usd": token_info.liquidity_usd,
        "fdv": token_info.fdv,
        "source": token_info.source,
    })
    print(f"[SIMULATED BUY] {token_info.symbol} @ ${token_info.price_usd:.6f} | FDV: ${token_info.fdv:,.0f}")

def evaluate_simulated_pnl(current_prices: Dict[str, float]) -> List[Dict]:
    """
    Evaluates current PnL for all simulated trades given current prices.
    :param current_prices: Dict mapping token addresses to live price
    :return: List of dicts with PnL data
    """
    results = []
    for trade in simulated_ledger:
        addr = trade["address"]
        if addr in current_prices:
            current_price = current_prices[addr]
            pnl = ((current_price - trade["buy_price"]) / trade["buy_price"]) * 100
            results.append({
                "symbol": trade["symbol"],
                "buy_price": trade["buy_price"],
                "current_price": current_price,
                "pnl_percent": pnl,
                "held_time_min": round((time.time() - trade["buy_time"]) / 60, 1),
            })
    return results

def get_simulated_pnl_report() -> str:
    """
    Generates a formatted report of current simulated PnLs.
    Requires an external live price update step (not included here).
    """
    # Stub: replace with real live prices later
    dummy_price_multiplier = 1.05  # assume +5% fake growth
    current_prices = {
        trade["address"]: trade["buy_price"] * dummy_price_multiplier
        for trade in simulated_ledger
    }
    pnl_data = evaluate_simulated_pnl(current_prices)

    if not pnl_data:
        return "📊 No simulated trades to report yet."

    lines = ["📊 *Simulated Trade Report*"]
    for entry in pnl_data:
        lines.append(
            f"• {entry['symbol']} | Bought @ ${entry['buy_price']:.4f}, Now: ${entry['current_price']:.4f} "
            f"→ *PnL:* {entry['pnl_percent']:+.2f}% after {entry['held_time_min']} min"
        )
    return "\n".join(lines)
