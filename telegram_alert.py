
# Filename: telegram_alert.py

import os
import requests
import config

def send_token_alert(token):
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN") or config.TELEGRAM_BOT_TOKEN
    chat_id = os.getenv("TELEGRAM_CHAT_ID") or config.TELEGRAM_CHAT_ID

    if not bot_token or not chat_id:
        print("[ERROR] Telegram credentials missing.")
        return

    name = token.name or "Unnamed"
    symbol = token.symbol or "?"
    address = token.address
    liquidity = token.liquidity_usd
    mcap = token.fdv
    pair = token.pair_id or "unknown"
    chart_link = f"https://dexscreener.com/solana/{pair}"
    solscan_link = f"https://solscan.io/token/{address}"

    msg = f"""
🚀 *New Token Detected*

*Name:* {name}
*Symbol:* `{symbol}`
*Liquidity:* ${liquidity:,.0f}
*Market Cap:* ${mcap:,.0f}
*Source:* {token.source or "unknown"}

📊 [View Chart]({chart_link})
🔍 [Solscan]({solscan_link})
    """.strip()

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": msg,
        "parse_mode": "Markdown",
        "disable_web_page_preview": False
    }

    try:
        resp = requests.post(url, data=payload)
        if resp.status_code != 200:
            print(f"[ERROR] Telegram alert failed: {resp.text}")
        else:
            print("[✅] Telegram alert sent.")
    except Exception as e:
        print(f"[ERROR] Telegram request failed: {e}")
