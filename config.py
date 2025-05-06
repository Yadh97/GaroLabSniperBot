# Filename: config.py

import os
from dotenv import load_dotenv
load_dotenv()

# --- Telegram Bot Config ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# --- Solana RPC Endpoint ---
RPC_URL = os.getenv("RPC_URL", "https://api.mainnet-beta.solana.com")

# --- Trading Wallet ---
PRIVATE_KEY = os.getenv("PRIVATE_KEY")  # base58 or JSON string of private key

# --- Auto Buy Settings ---
AUTO_BUY = os.getenv("AUTO_BUY", "0") == "1"
TRADE_SIZE_SOL = float(os.getenv("TRADE_SIZE_SOL", "0.25"))
SLIPPAGE_BPS = int(os.getenv("SLIPPAGE_BPS", "50"))  # 50 = 0.5%

# --- Token Filtering ---
MIN_LIQUIDITY_USD = float(os.getenv("MIN_LIQUIDITY_USD", "20000"))
MAX_FDV_USD = float(os.getenv("MAX_FDV_USD", "500000"))
TOP_HOLDER_MAX_PERCENT = float(os.getenv("TOP_HOLDER_MAX_PERCENT", "5"))

# --- Polling Rate ---
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", "10"))  # seconds

# --- Constants ---
SOL_MINT_ADDRESS = "So11111111111111111111111111111111111111112"

# --- RugCheck (no auth required) ---
RUGCHECK_BASE_URL = "https://api.rugcheck.xyz/tokens"
