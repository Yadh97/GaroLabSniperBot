# main.py

import threading
import time
import logging
from queue import Queue

from config import load_config
from websocket_listener import WebSocketListener
from token_monitor import TokenMonitor
from filters import TokenFilter
from trader import Trader
from simulated_trader import SimulatedTrader
from telegram_alert import TelegramNotifier
from token_cache import TokenCache

token_cache = TokenCache()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("Main")

def main():
    logger.info("🚀 Starting GaroLabSniperBot...")

    # Load config from JSON
    config = load_config()

    # Shared queue for token events
    event_queue = Queue()

    # Persistent cache
    token_cache = TokenCache()

    # Token filter
    token_filter = TokenFilter()

    # Telegram notifier
    telegram_notifier = None
    if config.get("ENABLE_TELEGRAM") and config.get("TELEGRAM_BOT_TOKEN") and config.get("TELEGRAM_CHAT_ID"):
        telegram_notifier = TelegramNotifier(
            config["TELEGRAM_BOT_TOKEN"],
            config["TELEGRAM_CHAT_ID"]
        )

    # Trader (simulated or real)
    if config.get("SIMULATION_MODE", True):
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
        config=config  # <-- pass config here
    )
    monitor_thread = threading.Thread(target=monitor.run, daemon=True)
    monitor_thread.start()

    # Main loop for performance report & health check
    last_report_time = time.time()
    report_interval = config.get("PERFORMANCE_REPORT_INTERVAL_HOURS", 6) * 3600

    try:
        while True:
            if time.time() - last_report_time > report_interval:
                monitor.send_performance_report()
                last_report_time = time.time()
            time.sleep(config.get("SCAN_INTERVAL_SECONDS", 10))
    except KeyboardInterrupt:
        logger.info("❌ Bot stopped by user.")
    finally:
        logger.info("🛑 Saving token cache...")
        token_cache.save()

if __name__ == "__main__":
    main()
