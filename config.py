# Filename: config.py

import os
from dotenv import load_dotenv

load_dotenv()

# === TELEGRAM ALERTING ===
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# === WALLET + RPC ===
WALLET_PRIVATE_KEY = os.getenv("WALLET_PRIVATE_KEY")
RPC_URL = os.getenv("RPC_URL", "https://api.mainnet-beta.solana.com")

# === SNIPING CONTROL ===
AUTO_BUY_ENABLED = os.getenv("AUTO_BUY_ENABLED", "false").lower() == "true"

# === FILTER CONFIGURATION ===
MIN_LIQUIDITY_USD = int(os.getenv("MIN_LIQUIDITY_USD", 20000))
MAX_FDV_USD = int(os.getenv("MAX_FDV_USD", 500000))
TOP_HOLDER_MAX_PERCENT = int(os.getenv("TOP_HOLDER_MAX_PERCENT", 5))

# === RUGCHECK ===
RUGCHECK_BASE_URL = "https://api.rugcheck.xyz/token"

# === MINT ADDRESSES ===
SOL_MINT_ADDRESS = "So11111111111111111111111111111111111111112"  # Wrapped SOL

# === MORALIS BACKUP API (optional) ===
MORALIS_API_KEY = os.getenv("MORALIS_API_KEY", "")

# === WORKING MODE ===
TEST_MODE = os.getenv("TEST_MODE", "true").lower() == "true"
