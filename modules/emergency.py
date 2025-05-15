from apscheduler.schedulers.background import BackgroundScheduler
from modules.utils import fetch_coinbase_price, send_telegram_message
import time

scheduler = BackgroundScheduler()
last_notified_price = None

def check_btc_price_change():
    global last_notified_price
    current_price = fetch_coinbase_price()

    if current_price is None:
        return

    if last_notified_price is None:
        last_notified_price = current_price
        return

    price_change_percent = abs(current_price - last_notified_price) / last_notified_price * 100

    if price_change_percent >= 3:
        # 3% 이상 변동일 때만 텔레그램 메시지 전송
        send_telegram_message(f"📛 BTC 가격 급변동 감지됨!\n💰 현재 BTC 가격: ${current_price:,.2f}\n📉 변화율: {price_change_percent:.2f}%")
        last_notified_price = current_price

def start_emergency_monitor():
    scheduler.add_job(check_btc_price_change, 'interval', minutes=5)
    scheduler.start()
