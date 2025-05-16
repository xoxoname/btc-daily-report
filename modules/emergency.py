import time
from apscheduler.schedulers.background import BackgroundScheduler
from modules.utils import fetch_coinbase_price, send_telegram_message
from modules.constants import EMERGENCY_THRESHOLD_PERCENT

scheduler = BackgroundScheduler()
previous_price = None

def check_btc_price_change():
    global previous_price
    try:
        current_price = fetch_coinbase_price()
        if previous_price is None:
            previous_price = current_price
            return
        change_percent = abs((current_price - previous_price) / previous_price) * 100
        if change_percent >= EMERGENCY_THRESHOLD_PERCENT:
            send_telegram_message(f"🚨 BTC 가격 급변 감지\n💰 현재 BTC 가격: ${current_price:,.2f}\n📉 변화율: {change_percent:.2f}%")
            previous_price = current_price
    except Exception as e:
        print(f"[ERROR] check_btc_price_change: {e}")

def start_emergency_monitor():
    scheduler.add_job(check_btc_price_change, 'interval', minutes=5)
    scheduler.start()
