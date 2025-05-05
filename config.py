import os

TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
PRIVATE_KEY = os.getenv('PRIVATE_KEY')
RPC_URL = os.getenv('RPC_URL')
MORALIS_API_KEY = os.getenv('MORALIS_API_KEY')
AUTO_BUY = bool(int(os.getenv("AUTO_BUY", "0")))
TRADE_SIZE_SOL = float(os.getenv("TRADE_SIZE_SOL", "1.0"))
SLIPPAGE_BPS = int(os.getenv("SLIPPAGE_BPS", "50"))
TAKE_PROFIT_MULTIPLE = float(os.getenv("TAKE_PROFIT_MULTIPLE", "2.0"))
POLL_INTERVAL = float(os.getenv("POLL_INTERVAL", "5"))
SOL_MINT_ADDRESS = "So11111111111111111111111111111111111111112"
DEXSCREENER_NEW_PAIRS_URL = "https://dexscreener.com/new-pairs"
PUMPFUN_NEW_TOKENS_URL = "https://solana-gateway.moralis.io/token/mainnet/exchange/pumpfun/new"
RUGCHECK_BASE_URL = "https://api.rugcheck.xyz/v1/tokens"
