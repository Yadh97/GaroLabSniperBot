
import time
import requests
import os

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

def send_alert(message):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    requests.post(url, data=payload)

def simulate_token_scan():
    # Simulated filtered token data
    message = '''
🚨 *GaroLab Test Alert (Full Logic)*

Token: $TESTCOIN 🧪
Liquidity: $19,200 ❌
Market Cap: $480k ✅
Top Holder: 7.2% ⚠️
RugCheck: SAFE ✅
Buzz Score: 68/100 ⚠️

Chart: https://dexscreener.com/solana/test
Contract: https://solscan.io/token/testcoin

This is a functional bot test. Real scanning logic can replace this block.
'''
    send_alert(message)

if __name__ == "__main__":
    while True:
        simulate_token_scan()
        time.sleep(120)  # Simulate scanning interval
