# token_monitor.py

import time
import logging
from threading import Thread
from filters import apply_all_filters
from token_cache import TokenCache
from telegram_alert import send_telegram_alert
from trader import SimulatedTrader, RealTrader

logger = logging.getLogger("TokenMonitor")

class TokenMonitor:
    def __init__(self, config, event_queue):
        self.config = config
        self.event_queue = event_queue
        self.cache = TokenCache(config)
        self.trader = SimulatedTrader(config) if config["SIMULATION_MODE"] else RealTrader(config)
        self.last_report_time = time.time()
        self.cumulative_filter_failures = {
            "liquidity": set(),
            "fdv": set(),
            "rugcheck": set(),
            "holders": set()
        }

    def start(self):
        Thread(target=self.run, daemon=True).start()

    def run(self):
        while True:
            try:
                if not self.event_queue.empty():
                    token = self.event_queue.get()
                    self.handle_token(token)

                # Report cumulative stats every 5 minutes
                if time.time() - self.last_report_time > 300:
                    self.print_cumulative_filter_stats()
                    self.last_report_time = time.time()

                time.sleep(0.25)
            except Exception as e:
                logger.error(f"Error in TokenMonitor loop: {e}")

    def handle_token(self, token):
        if not self.cache.should_track(token):
            return

        passed, reason = apply_all_filters(token, self.config)

        if not passed:
            if reason == "liquidity":
                self.cumulative_filter_failures["liquidity"].add(token.address)
            elif reason == "fdv":
                self.cumulative_filter_failures["fdv"].add(token.address)
            elif reason == "rugcheck":
                self.cumulative_filter_failures["rugcheck"].add(token.address)
            elif reason == "holders":
                self.cumulative_filter_failures["holders"].add(token.address)
            return

        self.cache.track(token)

        if self.config["AUTO_BUY_ENABLED"]:
            tx_result = self.trader.buy(token)
            if tx_result.success:
                send_telegram_alert(f"✅ Trade Executed: Bought {token.symbol} at {tx_result.price} SOL")

    def print_cumulative_filter_stats(self):
        logger.info("📊 *Cumulative Filter Rejection Summary*")
        for key, rejected in self.cumulative_filter_failures.items():
            logger.info(f"- {key.capitalize()} Failures: {len(rejected)} unique tokens")
