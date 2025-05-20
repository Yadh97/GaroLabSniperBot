# token_monitor.py

import time
import logging
from queue import Queue
from config import AUTO_BUY_ENABLED, SCAN_INTERVAL_SECONDS, RECHECK_INTERVAL_SECONDS
from token_cache import TokenCache
from filters import TokenFilter
from trader import Trader
from telegram_alert import TelegramNotifier

logger = logging.getLogger("TokenMonitor")

class TokenMonitor:
    def __init__(self, event_queue: Queue, token_cache: TokenCache,
                 token_filter: TokenFilter, trader: Trader,
                 notifier: TelegramNotifier = None):
        self.queue = event_queue
        self.cache = token_cache
        self.filter = token_filter
        self.trader = trader
        self.notifier = notifier

    def run(self):
        while True:
            try:
                self.consume_queue()
                self.recheck_cached_tokens()
                time.sleep(SCAN_INTERVAL_SECONDS)
            except Exception as e:
                logger.error(f"[Monitor Error] {e}")
                time.sleep(2)

    def consume_queue(self):
        while not self.queue.empty():
            token = self.queue.get()
            address = token.get("mint")
            if not self.cache.should_process(address):
                continue
            if self.filter.apply_filters(token):
                logger.info(f"[✅] {token.get('symbol', '?')} passed filters.")
                self.cache.mark_processed(address)
                if self.notifier:
                    self.notifier.send_token_alert(token)
                if AUTO_BUY_ENABLED:
                    self.trader.buy_token(token)
            else:
                logger.info(f"[❌] {token.get('symbol', '?')} did not pass filters.")
                self.cache.mark_filtered(address)

    def recheck_cached_tokens(self):
        to_check = self.cache.get_tokens_for_recheck(RECHECK_INTERVAL_SECONDS)
        logger.info(f"[RECHECK] {len(to_check)} tokens due for recheck.")
        for token in to_check:
            address = token.get("mint")
            if self.filter.apply_filters(token):
                logger.info(f"[RECHECK ✅] {token.get('symbol', '?')} passed filters.")
                self.cache.mark_processed(address)
                if self.notifier:
                    self.notifier.send_token_alert(token)
                if AUTO_BUY_ENABLED:
                    self.trader.buy_token(token)
            else:
                logger.info(f"[RECHECK ❌] {token.get('symbol', '?')} still invalid.")
                self.cache.mark_filtered(address)
