import requests
import config

def send_telegram_message(text: str):
    """Send a message via Telegram bot."""
    if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_CHAT_ID:
        print("[WARN] Telegram bot token or chat ID not configured. Skipping Telegram message.")
        return
    url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": config.TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "Markdown"  # Using Markdown for basic formatting
    }
    try:
        resp = requests.post(url, json=payload, timeout=5)
        if resp.status_code != 200:
            print(f"[ERROR] Telegram sendMessage failed: {resp.text}")
    except requests.RequestException as e:
        print(f"[ERROR] Exception sending Telegram message: {e}")

def format_token_alert(token, auto_buy=False, buy_txid=None):
    """Format the alert message text for a new token passing filters."""
    # Use Markdown formatting, ensure to escape any special characters in token name/symbol if needed
    name = token.name.replace("_", "\\_")
    symbol = token.symbol.replace("_", "\\_")
    text = f"*New Solana Token Detected!* 🎯\n"
    text += f"*Name:* {name} ({symbol})\n"
    text += f"*Price:* ${token.price_usd:.6f}\n"
    text += f"*Liquidity:* ${token.liquidity_usd:,.0f}\n"
    text += f"*Market Cap:* ${token.fdv:,.0f}\n"
    # If we have a DexScreener link or Solscan link, include it
    if token.pair_id:
        dex_url = f"https://dexscreener.com/solana/{token.pair_id}"
        text += f"[DexScreener Chart]({dex_url})\n"
    solscan_url = f"https://solscan.io/token/{token.address}"
    text += f"[Solscan]({solscan_url})"
    # Auto-buy info
    if auto_buy:
        if buy_txid:
            solscan_tx = f"https://solscan.io/tx/{buy_txid}"
            text += f"\n\n🤖 *Auto-Buy executed!* Bought ~{config.TRADE_SIZE_SOL} SOL of {symbol}.\n"
            text += f"Tx: [View on Solscan]({solscan_tx})"
        else:
            text += f"\n\n🤖 *Auto-Buy attempted!* (see logs for transaction status)"
    return text

def notify_new_token(token, auto_buy=False, buy_txid=None):
    """Send a Telegram alert about a new token that passed all filters (and optionally that we auto-bought)."""
    message = format_token_alert(token, auto_buy=auto_buy, buy_txid=buy_txid)
    send_telegram_message(message)
