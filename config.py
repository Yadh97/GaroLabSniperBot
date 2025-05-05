import os

# **API Endpoints and URLs**
DEXSCREENER_NEW_PAIRS_URL = "https://dexscreener.com/new-pairs"
PUMPFUN_NEW_TOKENS_URL = "https://solana-gateway.moralis.io/token/mainnet/exchange/pumpfun/new"  # Moralis Pump.fun API (requires API key)
RUGCHECK_BASE_URL = "https://api.rugcheck.xyz/v1/tokens"
JUPITER_QUOTE_URL = "https://quote-api.jup.ag/v6/quote"
JUPITER_SWAP_URL = "https://quote-api.jup.ag/v6/swap"
SOL_MINT_ADDRESS = "So11111111111111111111111111111111111111112"  # Special address representing SOL in Jupiter

# **Filter Thresholds**
MIN_LIQUIDITY_USD = 20000       # Minimum liquidity ($) required
MAX_FDV_USD = 500000           # Maximum fully diluted market cap ($) allowed
TOP_HOLDER_MAX_PERCENT = 5.0   # Top 10 holders must each hold less than 5% (percent)

# **Trade/Auto-Buy Settings**
AUTO_BUY = bool(int(os.getenv("AUTO_BUY", "0")))   # Enable auto-buy of tokens that pass filters (0/1 -> False/True)
TRADE_SIZE_SOL = float(os.getenv("TRADE_SIZE_SOL", "1.0"))  # How many SOL to use per trade when auto-buying
SLIPPAGE_BPS = int(os.getenv("SLIPPAGE_BPS", "50"))         # Slippage in basis points (e.g., 50 = 0.5%)
TAKE_PROFIT_MULTIPLE = float(os.getenv("TAKE_PROFIT_MULTIPLE", "2.0"))  # Target multiple for take-profit (e.g., 2.0 = 2x)
POLL_INTERVAL = float(os.getenv("POLL_INTERVAL", "5.0"))    # Interval in seconds to poll for new tokens and price updates

# **Environment Variables for Keys (to be set externally for security)**
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")     # Telegram bot token (from BotFather)
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")         # Telegram chat ID to send alerts to
MORALIS_API_KEY = os.getenv("MORALIS_API_KEY", "")           # Moralis API key for Pump.fun data (required)
RPC_URL = os.getenv("RPC_URL", "https://api.mainnet-beta.solana.com")  # Solana RPC endpoint (use a reliable one or your own node)
WALLET_PRIVATE_KEY = os.getenv("PRIVATE_KEY", "")            # Trading wallet's private key (base58 string or JSON array of ints)

# Note: Ensure sensitive keys (bot token, private key, Moralis API key, etc.) are set as environment variables 
# and not hard-coded here. This config simply reads them from the environment.
# Config file for environment variables
