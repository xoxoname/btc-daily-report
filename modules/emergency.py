# modules/emergency.py

import os
import requests
from apscheduler.schedulers.background import BackgroundScheduler
import pytz

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

last_price = None

def check_btc_price_change():
    global last_price
    try:
        # ✅ 테스트 메시지 전송
        message = (
            f"📛 *BTC 긴급 변동 감지 테스트!*\n"
            f"💰 현재 BTC 가격: $99,999.99\n"
            f"📉 변화율: 3.00%"
        )
        requests.get(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            params={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": message,
                "parse_mode": "Markdown"
            }
        )
    except Exception as e:
        print(f"[긴급 감지 에러]: {e}")

def start_emergency_monitor():
    seoul_tz = pytz.timezone('Asia/Seoul')
    scheduler = BackgroundScheduler(timezone=seoul_tz)
    scheduler.add_job(check_btc_price_change, 'interval', minutes=5)
    scheduler.start()
