import time
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
from data_sources import fetch_tokens
from filters import passes_filters
from notifier import send_alert
from trader import auto_buy

def main():
    print("🚀 GaroLabSniperBot is now running...\n")
    while True:
        try:
            tokens = fetch_tokens()
            for token in tokens:
                if passes_filters(token):
                    send_alert(token)
                    auto_buy(token)
                else:
                    print(f"❌ Token failed filters: {token['name']}")
        except Exception as e:
            print(f"⚠️ Error in main loop: {e}")
        time.sleep(60)  # Check every 60 seconds

if __name__ == "__main__":
    main()
