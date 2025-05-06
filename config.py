import os
from dotenv import load_dotenv
load_dotenv()
# -----------------------
# Sniper Filtering Config
# -----------------------

MIN_LIQUIDITY_USD = 20000         # Minimum liquidity in USD
MAX_FDV_USD = 500000              # Maximum fully diluted valuation
TOP_HOLDER_MAX_PERCENT = 5.0      # Top holder limit (%)

# -----------------------
# API and Network Config
# -----------------------

RPC_URL = os.getenv("RPC_URL", "https://api.mainnet-beta.solana.com")
RUGCHECK_BASE_URL = "https://api.rugcheck.xyz/v1/tokens"
MORALIS_API_KEY = os.getenv("MORALIS_API_KEY", "")
PUMPFUN_NEW_TOKENS_URL = "https://solana-gateway.moralis.io/token/mainnet/exchange/pumpfun/new"
DEXSCREENER_NEW_PAIRS_URL = "https://dexscreener.com/new-pairs"
SOL_MINT_ADDRESS = "So11111111111111111111111111111111111111112"

# -----------------------
# Telegram Bot Config
# -----------------------

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# -----------------------
# Auto-Buy Settings
# -----------------------

AUTO_BUY = os.getenv("AUTO_BUY", "0") == "1"
TRADE_SIZE_SOL = float(os.getenv("TRADE_SIZE_SOL", "1.0"))
SLIPPAGE_BPS = int(os.getenv("SLIPPAGE_BPS", "50"))
TAKE_PROFIT_MULTIPLE = float(os.getenv("TAKE_PROFIT_MULTIPLE", "2.0"))
POLL_INTERVAL = float(os.getenv("POLL_INTERVAL", "5"))

# -----------------------
# Wallet Key
# -----------------------

PRIVATE_KEY = os.getenv("PRIVATE_KEY", "")
