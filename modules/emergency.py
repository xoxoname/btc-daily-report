import time
import requests
from apscheduler.schedulers.background import BackgroundScheduler
from modules.utils import fetch_coinbase_price, send_telegram_message
from modules.constants import EMERGENCY_THRESHOLD_PERCENT

scheduler = BackgroundScheduler()
last_price = None

def check_btc_price_change():
    global last_price
    try:
        current_price = fetch_coinbase_price()
        if last_price is None:
            last_price = current_price
            return

        change_percent = abs((current_price - last_price) / last_price) * 100
        if change_percent >= EMERGENCY_THRESHOLD_PERCENT:
            # 실제 메시지 발송이 아닌 로그나 비동기 분석 처리 등으로 교체할 수 있음
            print(f"[긴급 감지] BTC 가격 급변: {change_percent:.2f}%")
        last_price = current_price

    except Exception as e:
        print(f"[에러] 긴급 감지 실패: {e}")

def start_emergency_monitor():
    scheduler.add_job(check_btc_price_change, 'interval', minutes=5)
    scheduler.start()
