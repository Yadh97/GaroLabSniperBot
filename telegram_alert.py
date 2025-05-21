# Filename: telegram_alert.py

import os
import requests
import logging
import config

logger = logging.getLogger("TelegramNotifier")

class TelegramNotifier:
    def __init__(self, bot_token: str = None, chat_id: str = None):
        cfg = config.load_config()
        self.bot_token = bot_token or os.getenv("TELEGRAM_BOT_TOKEN") or cfg.get("TELEGRAM_BOT_TOKEN", "")
        self.chat_id = chat_id or os.getenv("TELEGRAM_CHAT_ID") or cfg.get("TELEGRAM_CHAT_ID", "")

        if not self.bot_token or not self.chat_id:
            logger.error("[Telegram] Missing bot token or chat ID!")

    def send_token_alert(self, token):
        """
        Sends a formatted alert to a Telegram channel/user.
        Compatible with TokenInfo-style dict or object.
        """
        if not self.bot_token or not self.chat_id:
            return

        try:
            name = getattr(token, "name", token.get("name", "Unnamed"))
            symbol = getattr(token, "symbol", token.get("symbol", "?"))
            address = getattr(token, "address", token.get("mint") or token.get("address"))
            liquidity = float(getattr(token, "liquidity_usd", token.get("liquidity_usd", 0)))
            mcap = float(getattr(token, "fdv", token.get("fdv", 0)))
            source = getattr(token, "source", token.get("source", "unknown"))
            pair = getattr(token, "pair_id", token.get("pair_id", "unknown"))
            chart_link = f"https://dexscreener.com/solana/{pair}"
            solscan_link = f"https://solscan.io/token/{address}"

            msg = f"""
🚀 *New Token Detected!*

*Name:* {name}
*Symbol:* `{symbol}`
*Liquidity:* ${liquidity:,.0f}
*Market Cap:* ${mcap:,.0f}
*Source:* `{source}`

📊 [View Chart]({chart_link})
🔍 [View on Solscan]({solscan_link})
            """.strip()

            self.send_markdown(msg)

        except Exception as e:
            logger.error(f"[Telegram] Failed to send token alert: {e}")

    def send_markdown(self, text: str):
        """
        Sends a raw Markdown message.
        """
        if not self.bot_token or not self.chat_id:
            return

        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": "Markdown",
            "disable_web_page_preview": False
        }

        try:
            response = requests.post(url, data=payload)
            if response.status_code != 200:
                logger.error(f"[Telegram] Failed: {response.status_code} - {response.text}")
            else:
                logger.info("[Telegram] ✅ Message sent successfully.")
        except Exception as e:
            logger.error(f"[Telegram] Request exception: {e}")
