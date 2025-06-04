# Filename: token_monitor.py

import time
import logging
from queue import Queue
from token_cache import TokenCache
from filters import TokenFilter
from trader import Trader
from telegram_alert import TelegramNotifier
from config import load_config

logger = logging.getLogger("TokenMonitor")
config = load_config()

def normalize_token_event(event: dict) -> dict:
    """
    Converts a raw WebSocket or cached token dict into normalized structure
    expected by filters, trader, and alert modules.
    """
    try:
        sol_price = config.get("SOL_PRICE_USD", 150)  # fallback if missing

        return {
            "address": event.get("mint"),
            "symbol": event.get("symbol", "???"),
            "name": event.get("name", "Unknown"),
            "liquidity_usd": float(event.get("solAmount", 0)) * sol_price,
            "fdv": float(event.get("marketCapSol", 0)) * sol_price,
            "price_usd": float(event.get("price", 0)),
            "pair_id": event.get("pair_id", ""),
            "source": "pumpfun"
        }
    except Exception as e:
        logger.error(f"[Normalize Error] Failed to normalize token event: {e}")
        return {}


class TokenMonitor:
    def __init__(self, event_queue: Queue, token_cache: TokenCache,
                 token_filter: TokenFilter, trader: Trader,
                 notifier: TelegramNotifier = None,
                 config: dict = None):
        self.queue = event_queue
        self.cache = token_cache
        self.filter = token_filter
        self.trader = trader
        self.notifier = notifier
        self.config = config or {}
        self.scan_interval = self.config.get("SCAN_INTERVAL_SECONDS", 10)
        self.recheck_interval = self.config.get("RECHECK_INTERVAL_SECONDS", 300)
        self.auto_buy = self.config.get("AUTO_BUY_ENABLED", False)

    def run(self):
        while True:
            try:
                self.consume_queue()
                self.recheck_cached_tokens()
                time.sleep(self.scan_interval)
            except Exception as e:
                logger.error(f"[Monitor Error] {e}")
                time.sleep(2)

    def consume_queue(self):
        while not self.queue.empty():
            raw_event = self.queue.get()
            normalized = normalize_token_event(raw_event)
            address = normalized.get("address")
            if not address:
                continue
            self.cache.add_token_if_new(address, raw_event)
            if not self.cache.should_process(address):
                continue
            passed = self.filter.apply_filters(normalized)
            if passed:
                logger.info(f"[✅] {normalized['symbol']} passed filters.")
                self.cache.mark_processed(address)
                if self.notifier:
                    self.notifier.send_token_alert(normalized)
                if self.auto_buy:
                    self.trader.buy_token(normalized)
            else:
                logger.info(f"[❌] {normalized['symbol']} did not pass filters.")
                self.cache.mark_filtered(address)

    def recheck_cached_tokens(self):
        to_check = self.cache.get_due_for_check(self.recheck_interval)
        logger.info(f"[RECHECK] {len(to_check)} tokens due for recheck.")
        for entry in to_check:
            address = entry.get("address")
            raw_data = entry.get("data")
            if not address or not raw_data:
                continue
            normalized = normalize_token_event(raw_data)
            passed = self.filter.apply_filters(normalized)
            if passed:
                logger.info(f"[RECHECK ✅] {normalized['symbol']} passed filters.")
                self.cache.mark_processed(address)
                if self.notifier:
                    self.notifier.send_token_alert(normalized)
                if self.auto_buy:
                    self.trader.buy_token(normalized)
            else:
                logger.info(f"[RECHECK ❌] {normalized['symbol']} still invalid.")
                self.cache.mark_filtered(address)
