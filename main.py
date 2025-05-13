import time
import logging
import threading

import config
from token_monitor import TokenMonitor
from websocket_listener import listen_new_tokens
from token_cache import (
    add_token_if_new,
    cleanup_expired_tokens,
    update_check,
    get_due_for_check,
    get_ready_for_purge,
    remove_token,
    token_cache
)

def main():
    """Main entry point for the Solana Sniper Bot."""
    # Configure logging with timestamp and level from config
    log_level = getattr(logging, config.LOG_LEVEL.upper(), logging.INFO)
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    logging.info("Starting Solana Sniper Bot...")

    # Initialize shared token cache for communication between threads
 
    # Initialize the WebSocket listener (for new token/pool events) and token monitor
    ws_listener = WebSocketListener(config.RPC_WEBSOCKET_ENDPOINT, token_cache)
    token_monitor = TokenMonitor(token_cache)

    # Start the WebSocket listener and token monitor in separate threads
    ws_thread = threading.Thread(target=ws_listener.run, name="WebSocketListener", daemon=True)
    monitor_thread = threading.Thread(target=token_monitor.run, name="TokenMonitor", daemon=True)
    ws_thread.start()
    monitor_thread.start()
    logging.info("WebSocket listener and Token monitor threads started.")

    # Keep the main thread alive to allow background threads to run
    try:
        while True:
            time.sleep(60)
            # Optionally, we could monitor thread health here and restart if needed
    except KeyboardInterrupt:
        logging.info("Shutdown signal received. Stopping bot...")
        # Graceful shutdown: instruct threads to stop (if implemented) and join
        token_monitor.stop()  # If TokenMonitor has a stop mechanism
        ws_listener.stop()    # If WebSocketListener has a stop mechanism
        ws_thread.join(timeout=5)
        monitor_thread.join(timeout=5)
        logging.info("Bot stopped.")

if __name__ == "__main__":
    main()
