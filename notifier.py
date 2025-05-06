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
        "parse_mode": "Markdown",  # Markdown formatting
        "disable_web_page_preview": False
    }
    try:
        resp = requests.post(url, json=payload, timeout=5)
        if resp.status_code != 200:
            print(f"[ERROR] Telegram sendMessage failed: {resp.text}")
    except requests.RequestException as e:
        print(f"[ERROR] Exception sending Telegram message: {e}")

def format_token_alert(token, auto_buy=False, buy_txid=None):
    """Format the alert message text for a new token passing filters."""
    # Escape Markdown-sensitive characters
    def escape_md(text):
        return text.replace('_', '\\_').replace('*', '\\*').replace('[', '\\[').replace('`', '\\`')

    name = escape_md(token.name)
    symbol = escape_md(token.symbol)
    price = f"${token.price_usd:,.6f}"
    liquidity = f"${token.liquidity_usd:,.0f}"
    fdv = f"${token.fdv:,.0f}"

    text = f"🚀 *New Solana Token Detected!*\n\n"
    text += f"*Name:* {name}\n"
    text += f"*Symbol:* `{symbol}`\n"
    text += f"*Price:* {price}\n"
    text += f"*Liquidity:* {liquidity}\n"
    text += f"*Market Cap:* {fdv}\n"

    # Add links
    if token.pair_id:
        dex_url = f"https://dexscreener.com/solana/{token.pair_id}"
        text += f"[📈 DexScreener Chart]({dex_url})\n"

    solscan_url = f"https://solscan.io/token/{token.address}"
    text += f"[🔎 View on Solscan]({solscan_url})"

    # Optional: Auto-buy status
    if auto_buy:
        if buy_txid:
            solscan_tx = f"https://solscan.io/tx/{buy_txid}"
            text += f"\n\n✅ *Auto-Buy Executed!* Bought ~{config.TRADE_SIZE_SOL} SOL of `{symbol}`.\n"
            text += f"[🔄 Transaction on Solscan]({solscan_tx})"
        else:
            text += f"\n\n⚠️ *Auto-Buy attempted.* Check logs for confirmation."

    return text

def notify_new_token(token, auto_buy=False, buy_txid=None):
    """Send a Telegram alert about a new token that passed all filters."""
    message = format_token_alert(token, auto_buy=auto_buy, buy_txid=buy_txid)
    send_telegram_message(message)
