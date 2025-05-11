
# Filename: config.py

import os
from dotenv import load_dotenv

load_dotenv()

# Solana network and wallet configuration
RPC_URL = os.getenv("SOLANA_RPC_URL", "https://api.mainnet-beta.solana.com")
WALLET_PRIVATE_KEY = os.getenv("WALLET_PRIVATE_KEY", "")

# Telegram bot configuration
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# Filtering thresholds
MIN_LIQUIDITY_USD = float(os.getenv("MIN_LIQUIDITY_USD", 20000))
MAX_FDV_USD = float(os.getenv("MAX_FDV_USD", 500000))
TOP_HOLDER_MAX_PERCENT = float(os.getenv("TOP_HOLDER_MAX_PERCENT", 5))

# RugCheck API base
RUGCHECK_BASE_URL = os.getenv("RUGCHECK_BASE_URL", "https://api.rugcheck.xyz/token")

# Price assumptions
SOL_PRICE_USD = float(os.getenv("SOL_PRICE_USD", 150.0))  # Used for FDV and liquidity calcs

# Behavior toggles
AUTO_BUY_ENABLED = os.getenv("AUTO_BUY_ENABLED", "false").lower() == "true"

# Cache cleanup interval (seconds)
CACHE_CLEANUP_INTERVAL_SECONDS = int(os.getenv("CACHE_CLEANUP_INTERVAL_SECONDS", 300))
