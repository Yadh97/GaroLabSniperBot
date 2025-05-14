
# Filename: config.py

import os
from dotenv import load_dotenv

load_dotenv()

# Solana network and wallet configuration
RPC_HTTP_ENDPOINT = os.getenv("SOLANA_RPC_URL", "https://mainnet.helius-rpc.com/?api-key=a3688971-6f9a-4bda-8001-9c618a420cf8")
RPC_WEBSOCKET_ENDPOINT = os.getenv("RPC_WEBSOCKET_ENDPOINT", "wss://mainnet.helius-rpc.com/?api-key=a3688971-6f9a-4bda-8001-9c618a420cf8")
COMMITMENT = os.getenv("COMMITMENT_LEVEL", "finalized")

WALLET_PRIVATE_KEY = os.getenv("WALLET_PRIVATE_KEY", "")

# Telegram bot configuration
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "7429739371:AAHzTsw2RlNdIW_mC8zLADGTpdXn0ENsaH4")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "5262711263")

MIN_LIQUIDITY_USD = float(os.getenv("MIN_LIQUIDITY_USD", 20000))
MAX_FDV_USD = float(os.getenv("MAX_FDV_USD", 500_000))# Min liquidity to accept
MAX_FDV = float(os.getenv("MAX_FDV_USD", 5000000))                         # Max FDV (Fully Diluted Valuation)
MAX_HOLDER_PERCENT = float(os.getenv("TOP_HOLDER_MAX_PERCENT", 5))        # Max % for top holder (normal tokens)
MAX_HOLDER_PERCENT_NEW = float(os.getenv("TOP_HOLDER_MAX_PERCENT_NEW", 80))  # Max % for top holder if <5 mins old

# === RugCheck API ===
RUGCHECK_BASE_URL = os.getenv("RUGCHECK_BASE_URL", "https://api.rugcheck.xyz/token")

# === Price baseline ===
SOL_PRICE_USD = float(os.getenv("SOL_PRICE_USD", 150.0))  # Fallback price estimate

# === Behavior toggles ===
AUTO_BUY_ENABLED = os.getenv("AUTO_BUY_ENABLED", "false").lower() == "true"

# === Runtime behavior ===
CACHE_CLEANUP_INTERVAL_SECONDS = int(os.getenv("CACHE_CLEANUP_INTERVAL_SECONDS", 300))
RECHECK_WINDOW_SEC = int(os.getenv("RECHECK_WINDOW_SEC", 300))  # Retry failed tokens for 5 mins

# === Logging ===
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# === Retry logic ===
RPC_MAX_RETRIES = int(os.getenv("RPC_MAX_RETRIES", 5))         # Max retries for rate limits or failures
RPC_BACKOFF_FACTOR = float(os.getenv("RPC_BACKOFF_FACTOR", 1)) # Seconds between exponential backoffs
