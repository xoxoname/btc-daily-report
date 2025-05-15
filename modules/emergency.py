import os
import requests

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

def check_btc_price_change():
    try:
        message = (
            f"📛 *BTC 긴급 변동 감지 테스트!*\n"
            f"💰 현재 BTC 가격: $99,999.99\n"
            f"📉 변화율: 3.00%"
        )
        response = requests.get(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            params={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": message,
                "parse_mode": "Markdown"
            }
        )
        print("[전송 성공]", response.status_code, response.text)
    except Exception as e:
        print(f"[긴급 감지 에러]: {e}")
