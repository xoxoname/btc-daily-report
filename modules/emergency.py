import requests
import time
from apscheduler.schedulers.background import BackgroundScheduler
from modules.constants import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID
from modules.utils import format_currency

last_price = None

def fetch_current_btc_price():
    try:
        response = requests.get("https://api.coinbase.com/v2/prices/spot?currency=USD")
        return float(response.json()["data"]["amount"])
    except Exception as e:
        print(f"[BTC 가격 조회 실패]: {e}")
        return None

def send_telegram_alert(message: str):
    try:
        requests.get(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            params={"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"},
            timeout=5
        )
    except Exception as e:
        print(f"[텔레그램 전송 오류]: {e}")

def check_btc_price_change():
    global last_price
    current_price = fetch_current_btc_price()
    if current_price is None:
        return

    if last_price is not None:
        change_percent = ((current_price - last_price) / last_price) * 100
        if abs(change_percent) >= 2.5:
            direction = "급등" if change_percent > 0 else "급락"
            message = (
                f"🚨 *BTC {direction} 감지!*\n"
                f"💰 현재 BTC 가격: {format_currency(current_price)}\n"
                f"📊 변화율: {change_percent:.2f}%"
            )
            send_telegram_alert(message)

    last_price = current_price

def start_emergency_monitor():
    scheduler = BackgroundScheduler(timezone="Asia/Seoul")
    scheduler.add_job(check_btc_price_change, 'interval', minutes=5)
    scheduler.start()
