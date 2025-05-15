# modules/emergency.py

import requests
import time
from apscheduler.schedulers.background import BackgroundScheduler
from modules.constants import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID
from modules.utils import fetch_coinbase_price, fetch_latest_event_summary_kr

last_price = None

def check_btc_price_change():
    global last_price
    try:
        price = fetch_coinbase_price()
        if price is None:
            return

        if last_price is None:
            last_price = price
            return

        change_percent = abs(price - last_price) / last_price * 100

        if change_percent >= 2:
            summary_kr = fetch_latest_event_summary_kr()
            message = (
                f"🚨 *BTC 급변동 감지!*\n"
                f"💰 현재 BTC 가격: ${price:,.2f}\n"
                f"📈 변화율: {change_percent:.2f}%\n"
                f"📰 감지된 이슈: {summary_kr}"
            )
            requests.get(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                params={"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}
            )
            last_price = price
    except Exception as e:
        print(f"[긴급 감지 에러]: {e}")

def start_emergency_monitor():
    scheduler = BackgroundScheduler(timezone="Asia/Seoul")
    scheduler.add_job(check_btc_price_change, 'interval', minutes=5)
    scheduler.start()
