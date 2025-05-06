import requests
import config

def send_telegram_message(text: str):
    """Send a Markdown-formatted Telegram alert."""
    if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_CHAT_ID:
        print("[WARN] Telegram not configured.")
        return
    url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": config.TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": False
    }
    try:
        resp = requests.post(url, json=payload, timeout=5)
        if resp.status_code != 200:
            print(f"[ERROR] Telegram sendMessage failed: {resp.text}")
    except Exception as e:
        print(f"[ERROR] Telegram error: {e}")

def format_token_alert(token, auto_buy=False, buy_txid=None):
    """Format a complete token alert with Markdown-safe fields."""
    def escape_md(text):
        return text.replace("_", "\\_").replace("*", "\\*").replace("[", "\\[").replace("]", "\\]").replace("`", "\\`")

    name = escape_md(token.name)
    symbol = escape_md(token.symbol)
    price = f"${token.price_usd:,.6f}"
    liquidity = f"${token.liquidity_usd:,.0f}"
    fdv = f"${token.fdv:,.0f}"

    msg = f"🚀 *New Solana Token Detected!*\n\n"
    msg += f"*Name:* {name}\n"
    msg += f"*Symbol:* `{symbol}`\n"
    msg += f"*Price:* {price}\n"
    msg += f"*Liquidity:* {liquidity}\n"
    msg += f"*Market Cap:* {fdv}\n"

    # Add links
    if token.pair_id:
        msg += f"[📈 View Chart on DexScreener](https://dexscreener.com/solana/{token.pair_id})\n"
    msg += f"[🔎 View on Solscan](https://solscan.io/token/{token.address})"

    # Optional: Buy details
    if auto_buy:
        if buy_txid:
            tx_url = f"https://solscan.io/tx/{buy_txid}"
            msg += f"\n\n✅ *Auto-Buy Executed!*\n[🔄 Transaction Link]({tx_url})"
        else:
            msg += f"\n\n⚠️ *Auto-Buy Attempted* (no txid returned)"

    return msg

def notify_new_token(token, auto_buy=False, buy_txid=None):
    """Send Telegram alert for any filtered token."""
    text = format_token_alert(token, auto_buy, buy_txid)
    send_telegram_message(text)
