import requests
from apscheduler.schedulers.background import BackgroundScheduler
from modules.constants import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, EMERGENCY_THRESHOLD_PERCENT
from modules.utils import fetch_coinbase_price

scheduler = BackgroundScheduler()
last_price = None

def check_btc_price_change():
    global last_price
    current_price = fetch_coinbase_price()
    if last_price is None:
        last_price = current_price
        return

    percent_change = abs((current_price - last_price) / last_price) * 100
    if percent_change >= EMERGENCY_THRESHOLD_PERCENT:
        # 긴급 알림 전송 로직 제거됨 (테스트 알림 방지 목적)
        last_price = current_price

def start_emergency_monitor():
    scheduler.add_job(check_btc_price_change, 'interval', minutes=5)
    scheduler.start()
