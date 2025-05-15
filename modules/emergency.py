import os
import requests
from apscheduler.schedulers.background import BackgroundScheduler
from modules.constants import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID

last_price = None

def check_btc_price_change():
    global last_price
    try:
        # 테스트용 고정 가격
        current_price = 99999.99
        if last_price is None:
            last_price = current_price
            return

        change_percent = abs((current_price - last_price) / last_price) * 100

        if change_percent >= 2.0:  # 예시: 2% 이상 변화 감지
            message = (
                f"📛 *BTC 긴급 변동 감지!*\n"
                f"💰 현재 BTC 가격: ${current_price:,.2f}\n"
                f"📉 변화율: {change_percent:.2f}%"
            )
            requests.get(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                params={"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}
            )

        last_price = current_price
    except Exception as e:
        print(f"[긴급 감지 에러]: {e}")

def start_emergency_monitor():
    scheduler = BackgroundScheduler()
    scheduler.add_job(check_btc_price_change, 'interval', minutes=5)
    scheduler.start()
