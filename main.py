# main.py

import threading
import time
import logging
from queue import Queue

from config import (
    SIMULATION_MODE,
    TELEGRAM_ENABLED,
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_CHAT_ID,
    SCAN_INTERVAL_SECONDS,
    PERFORMANCE_REPORT_INTERVAL_HOURS,
)

from websocket_listener import WebSocketListener
from token_monitor import TokenMonitor
from token_cache import TokenCache
from filters import TokenFilter
from trader import Trader
from simulated_trader import SimulatedTrader
from telegram_alert import TelegramNotifier

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("Main")

def main():
    logger.info("🚀 Starting GaroLabSniperBot...")

    # Shared queue for token events
    event_queue = Queue()

    # Persistent cache
    token_cache = TokenCache()

    # Token filter
    token_filter = TokenFilter()

    # Telegram notifier
    telegram_notifier = None
    if TELEGRAM_ENABLED and TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        telegram_notifier = TelegramNotifier(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID)

    # Trader (simulated or real)
    if SIMULATION_MODE:
        logger.info("🧪 Running in SIMULATION mode")
        trader = SimulatedTrader()
    else:
        logger.info("💰 Running in REAL TRADING mode")
        trader = Trader()

    # WebSocket listener for new tokens
    listener = WebSocketListener(event_queue=event_queue)
    listener_thread = threading.Thread(target=listener.run, daemon=True)
    listener_thread.start()

    # Token monitor (filters, decisions, trading, alerts)
    monitor = TokenMonitor(
        event_queue=event_queue,
        token_cache=token_cache,
        token_filter=token_filter,
        trader=trader,
        notifier=telegram_notifier,
    )
    monitor_thread = threading.Thread(target=monitor.run, daemon=True)
    monitor_thread.start()

    # Main loop for performance report & health check
    last_report_time = time.time()
    report_interval = PERFORMANCE_REPORT_INTERVAL_HOURS * 3600

    try:
        while True:
            if time.time() - last_report_time > report_interval:
                monitor.send_performance_report()
                last_report_time = time.time()
            time.sleep(SCAN_INTERVAL_SECONDS)
    except KeyboardInterrupt:
        logger.info("❌ Bot stopped by user.")
    finally:
        logger.info("🛑 Saving token cache...")
        token_cache.save()

if __name__ == "__main__":
    main()
