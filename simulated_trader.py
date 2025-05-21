# Filename: simulated_trader.py

import json
import time
import logging
import random
from typing import Dict, List, Any, Optional

from config import load_config
from telegram_alert import TelegramNotifier

logger = logging.getLogger("SimulatedTrader")


class SimulatedTrader:
    def __init__(self, config_data=None, notifier: Optional[TelegramNotifier] = None):
        self.config = config_data or load_config()
        self.notifier = notifier
        self.positions_file = self.config.get("POSITIONS_FILE", "simulated_positions.json")
        self.positions: Dict[str, Dict[str, Any]] = {}
        self.load_positions()
        self.tracker = None  # Will be injected later

    def load_positions(self):
        try:
            with open(self.positions_file, "r") as f:
                self.positions = json.load(f)
            logger.info(f"[SIM] Loaded {len(self.positions)} simulated positions.")
        except Exception:
            self.positions = {}

    def save_positions(self):
        try:
            with open(self.positions_file, "w") as f:
                json.dump(self.positions, f, indent=2)
        except Exception as e:
            logger.error(f"[SIM] Failed to save positions: {e}")

    async def buy_token(self, token_info, amount_sol: float = 0.5, slippage_percent: float = 3.0) -> Dict[str, Any]:
        address = token_info.address
        symbol = token_info.symbol
        name = token_info.name
        buy_price = token_info.price_usd or random.uniform(0.0001, 0.01)

        if address in self.positions:
            logger.info(f"[SIM] Already holding {symbol}, skipping simulated buy.")
            return {"success": False, "error": "Already in position"}

        token_amount = amount_sol / buy_price
        self.positions[address] = {
            "symbol": symbol,
            "name": name,
            "amount_sol": amount_sol,
            "token_amount": token_amount,
            "buy_price": buy_price,
            "timestamp": time.time(),
            "status": "open"
        }
        self.save_positions()

        logger.info(f"[SIM ✅] Bought {symbol} at ${buy_price:.6f} (amount: {amount_sol} SOL)")

        if self.notifier:
            msg = f"""
🛒 *Simulated BUY*
*Name:* {name}
*Symbol:* `{symbol}`
*Amount:* {amount_sol:.2f} SOL
*Qty:* {token_amount:.2f}
*Price:* ${buy_price:.6f}
📅 Time: <code>{time.strftime('%Y-%m-%d %H:%M:%S')}</code>
🧪 Mode: Simulation
            """.strip()
            self.notifier.send_message(msg)

        # Inject live tracking into tracker if available
        if self.tracker:
            self.tracker.track(address, buy_price, token_amount, symbol)

        return {
            "success": True,
            "token_address": address,
            "symbol": symbol,
            "amount_sol": amount_sol,
            "price": buy_price,
            "token_amount": token_amount
        }

    async def sell_token(self, token_address: str, current_price: float = None) -> Dict[str, Any]:
        pos = self.positions.get(token_address)
        if not pos or pos["status"] != "open":
            logger.warning(f"[SIM] No active position for {token_address}")
            return {"success": False, "error": "Position not found"}

        symbol = pos["symbol"]
        name = pos.get("name", "?")
        buy_price = pos["buy_price"]
        token_amount = pos["token_amount"]

        if current_price is None:
            current_price = buy_price * (1 + random.uniform(-0.2, 0.5))

        pnl_percent = ((current_price - buy_price) / buy_price) * 100
        sol_returned = current_price * token_amount
        profit_sol = sol_returned - pos["amount_sol"]

        pos.update({
            "sell_price": current_price,
            "pnl_percent": pnl_percent,
            "sol_returned": sol_returned,
            "profit_sol": profit_sol,
            "closed_at": time.time(),
            "status": "closed"
        })
        self.save_positions()

        logger.info(f"[SIM ✅] Sold {symbol}: PnL = {pnl_percent:.2f}%, Profit = {profit_sol:.3f} SOL")

        if self.notifier:
            held_time = int(pos["closed_at"] - pos["timestamp"])
            minutes = held_time // 60
            seconds = held_time % 60

            msg = f"""
💰 *Simulated SELL*
*Name:* {name}
*Symbol:* `{symbol}`
*Sell Price:* ${current_price:.6f}
*PnL:* {pnl_percent:+.2f}%
*Profit:* {profit_sol:.3f} SOL
*Returned:* {sol_returned:.3f} SOL
*Held:* {minutes}m {seconds}s
🧪 Mode: Simulation
            """.strip()
            self.notifier.send_message(msg)

        return {
            "success": True,
            "symbol": symbol,
            "token_amount": token_amount,
            "buy_price": buy_price,
            "sell_price": current_price,
            "pnl_percent": pnl_percent,
            "sol_returned": sol_returned,
            "profit_sol": profit_sol
        }

    def get_open_positions(self) -> List[Dict[str, Any]]:
        return [p for p in self.positions.values() if p["status"] == "open"]

    def get_closed_positions(self) -> List[Dict[str, Any]]:
        return [p for p in self.positions.values() if p["status"] == "closed"]

    def get_position_performance_summary(self) -> Dict[str, Any]:
        closed = self.get_closed_positions()
        if not closed:
            return {
                "total_trades": 0,
                "winning_trades": 0,
                "avg_profit": 0,
                "avg_loss": 0,
                "total_profit_loss": 0,
                "best_trade": None
            }

        profits = [p["pnl_percent"] for p in closed if p["pnl_percent"] > 0]
        losses = [p["pnl_percent"] for p in closed if p["pnl_percent"] <= 0]
        best = max(closed, key=lambda p: p["pnl_percent"])

        return {
            "total_trades": len(closed),
            "winning_trades": len(profits),
            "avg_profit": sum(profits) / len(profits) if profits else 0,
            "avg_loss": sum(losses) / len(losses) if losses else 0,
            "total_profit_loss": sum(p["profit_sol"] for p in closed),
            "best_trade": best
        }
