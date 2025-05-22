# Filename: main.py

import threading
import time
import logging
from queue import Queue
import asyncio

from config import load_config
from websocket_listener import WebSocketListener
from token_monitor import TokenMonitor
from filters import TokenFilter
from trader import Trader
from simulated_trader import SimulatedTrader
from telegram_alert import TelegramNotifier
from token_cache import TokenCache
from performance_reporter import start_reporter_background_thread
from position_tracker import PositionTracker

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("Main")

def main():
    logger.info("🚀 Starting GaroLabSniperBot...")

    # Load runtime config
    config = load_config()

    # Initialize event queue
    event_queue = Queue()

    # Create token cache
    token_cache = TokenCache()

    # Token filtering logic
    token_filter = TokenFilter()

    # Telegram Notifier (optional)
    telegram_notifier = None
    if config.get("ENABLE_TELEGRAM") and config.get("TELEGRAM_BOT_TOKEN") and config.get("TELEGRAM_CHAT_ID"):
        telegram_notifier = TelegramNotifier(
            config["TELEGRAM_BOT_TOKEN"],
            config["TELEGRAM_CHAT_ID"]
        )

    # Trader instance (simulated or real)
    if config.get("SIMULATION_MODE", True):
        logger.info("🧪 Running in SIMULATION mode")
        trader = SimulatedTrader(config_data=config, notifier=telegram_notifier)
    else:
        logger.info("💰 Running in REAL TRADING mode")
        trader = Trader(config)

    # Start position tracker (PnL + auto-sell)
    tracker = PositionTracker(trader=trader, notifier=telegram_notifier)
    threading.Thread(target=lambda: asyncio.run(tracker.run()), daemon=True).start()

    # WebSocket callback
    def handle_new_token(token_event: dict):
        event_queue.put(token_event)

    # WebSocket listener
    listener = WebSocketListener(on_token_callback=handle_new_token)
    threading.Thread(target=listener.run, daemon=True).start()

    # Token monitor
    monitor = TokenMonitor(
        event_queue=event_queue,
        token_cache=token_cache,
        token_filter=token_filter,
        trader=trader,
        notifier=telegram_notifier,
        config=config
    )
    monitor.tracker = tracker
    threading.Thread(target=monitor.run, daemon=True).start()

    # Start automated 30-min performance reporter
    start_reporter_background_thread(config=config, notifier=telegram_notifier)

    # ✅ Add visibility heartbeat every 5 minutes
    def visibility_heartbeat():
        while True:
            try:
                stats = token_cache.get_cache_statistics()
                message = (
                    f"📊 *Bot Visibility Report*\n"
                    f"*Total Tokens Seen:* {stats['seen']}\n"
                    f"*Tracked:* {stats['tracked']}\n"
                    f"*Filtered:* {stats['filtered']}"
                )
                if telegram_notifier:
                    telegram_notifier.send_message(message)
                else:
                    logger.info(message)
            except Exception as e:
                logger.error(f"[Heartbeat Error] {e}")
            time.sleep(300)

    threading.Thread(target=visibility_heartbeat, daemon=True).start()

    # Fallback hourly report (in case 30-min reporter fails)
    last_report_time = time.time()
    report_interval = config.get("PERFORMANCE_REPORT_INTERVAL_HOURS", 6) * 3600
    scan_interval = config.get("SCAN_INTERVAL_SECONDS", 10)

    try:
        while True:
            if time.time() - last_report_time > report_interval:
                monitor.send_performance_report()
                last_report_time = time.time()
            time.sleep(scan_interval)
    except KeyboardInterrupt:
        logger.info("❌ Bot stopped by user.")
    finally:
        logger.info("🛑 Saving token cache before shutdown...")
        token_cache.save()

if __name__ == "__main__":
    main()
