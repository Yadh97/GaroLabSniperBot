# Filename: token_monitor.py

import time
import logging
from queue import Queue
from token_cache import TokenCache
from filters import TokenFilter
from trader import Trader
from telegram_alert import TelegramNotifier

logger = logging.getLogger("TokenMonitor")

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
            token = self.queue.get()
            address = token.get("mint")
            if not address:
                continue
            self.cache.add_token_if_new(address, token)
            if not self.cache.should_process(address):
                continue
            if self.filter.apply_filters(token):
                logger.info(f"[✅] {token.get('symbol', '?')} passed filters.")
                self.cache.mark_processed(address)
                if self.notifier:
                    self.notifier.send_token_alert(token)
                if self.auto_buy:
                    self.trader.buy_token(token)
            else:
                logger.info(f"[❌] {token.get('symbol', '?')} did not pass filters.")
                self.cache.mark_filtered(address)

    def recheck_cached_tokens(self):
        to_check = self.cache.get_due_for_check(self.recheck_interval)
        logger.info(f"[RECHECK] {len(to_check)} tokens due for recheck.")
        for token in to_check:
            address = token.get("address")
            event_data = token.get("data")
            if not address or not event_data:
                continue
            if self.filter.apply_filters(event_data):
                logger.info(f"[RECHECK ✅] {event_data.get('symbol', '?')} passed filters.")
                self.cache.mark_processed(address)
                if self.notifier:
                    self.notifier.send_token_alert(event_data)
                if self.auto_buy:
                    self.trader.buy_token(event_data)
            else:
                logger.info(f"[RECHECK ❌] {event_data.get('symbol', '?')} still invalid.")
                self.cache.mark_filtered(address)
