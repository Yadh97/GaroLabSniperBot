# Filename: position_tracker.py

import asyncio
import time
import logging
from typing import Dict, Any, Optional

from config import load_config
from telegram_alert import TelegramNotifier

logger = logging.getLogger("PositionTracker")

class PositionTracker:
    def __init__(self, trader, notifier: Optional[TelegramNotifier] = None):
        self.trader = trader
        self.notifier = notifier
        self.config = load_config()
        self.tracked_positions: Dict[str, Dict[str, Any]] = {}  # token_address -> buy info
        self.check_interval = 1  # seconds
        self.stop_loss_pct = 50.0  # default stop loss (50%)
        self.take_profit_pct = 100.0  # default TP at 2x
        self.trailing_stop_pct = 20.0  # trigger sell if price drops 20% from peak after 50% gain
        self.max_hold_seconds = 600  # max 10 minutes

    def track(self, token_address: str, buy_price: float, token_amount: float, symbol: str):
        logger.info(f"[TRACKING] Start monitoring {symbol} ({token_address})")
        self.tracked_positions[token_address] = {
            "buy_price": buy_price,
            "amount": token_amount,
            "symbol": symbol,
            "start_time": time.time(),
            "peak_price": buy_price,
        }

    async def run(self):
        while True:
            try:
                await self.check_positions()
            except Exception as e:
                logger.error(f"[PositionTracker Error] {e}")
            await asyncio.sleep(self.check_interval)

    async def check_positions(self):
        now = time.time()
        for address, pos in list(self.tracked_positions.items()):
            # Get current price (from token info)
            result = await self.trader.get_live_token_price(address)
            if not result or not result.get("price"):
                logger.warning(f"[TRACK] Unable to get live price for {address}")
                continue

            current_price = result["price"]
            pnl_pct = ((current_price - pos["buy_price"]) / pos["buy_price"]) * 100
            symbol = pos["symbol"]
            logger.info(f"[TRACK] {symbol} PnL = {pnl_pct:.2f}%")

            # Update peak price
            if current_price > pos["peak_price"]:
                pos["peak_price"] = current_price

            # Check sell conditions
            hold_time = now - pos["start_time"]
            peak_price = pos["peak_price"]

            should_sell = False
            reason = ""

            if pnl_pct >= self.take_profit_pct:
                should_sell = True
                reason = "Take Profit"
            elif pnl_pct >= 50 and current_price < peak_price * (1 - self.trailing_stop_pct / 100):
                should_sell = True
                reason = "Trailing Stop"
            elif pnl_pct <= -self.stop_loss_pct:
                should_sell = True
                reason = "Stop Loss"
            elif hold_time > self.max_hold_seconds:
                should_sell = True
                reason = "Max Hold Time"

            if should_sell:
                result = await self.trader.sell_token(address, current_price)
                if result["success"]:
                    pnl = result["pnl_percent"]
                    sol_profit = result["profit_sol"]
                    msg = f"\u274c *{symbol}* auto-sold (reason: {reason})\nPnL: `{pnl:.2f}%`, Profit: `{sol_profit:.4f} SOL`"
                    if self.notifier:
                        self.notifier.send_markdown(msg)
                    logger.info(f"[SELL] {symbol} sold due to {reason}. PnL = {pnl:.2f}%")
                else:
                    logger.error(f"[SELL FAIL] Failed to sell {symbol}: {result.get('error')}")
                del self.tracked_positions[address]
