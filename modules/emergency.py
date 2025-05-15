import requests
from apscheduler.schedulers.background import BackgroundScheduler
from modules.constants import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID

# 초기 이전 가격 설정
last_price = None

def check_btc_price_change():
    global last_price
    try:
        response = requests.get("https://api.coindesk.com/v1/bpi/currentprice/BTC.json", timeout=5)
        data = response.json()
        current_price = float(data["bpi"]["USD"]["rate"].replace(",", ""))

        # 초기화
        if last_price is None:
            last_price = current_price
            return

        # 변동률 계산
        change_percent = abs(current_price - last_price) / last_price
        if change_percent >= 0.02:  # 2% 이상 변동
            message = (
                f"📛 *BTC 긴급 변동 감지!*\n"
                f"💰 현재 BTC 가격: ${current_price:,.2f}\n"
                f"📉 변화율: {change_percent * 100:.2f}%"
            )
            requests.get(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                params={"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}
            )

        last_price = current_price

    except Exception as e:
        print(f"[긴급 감지 에러]: {e}")

def start_emergency_monitor():
    scheduler = BackgroundScheduler(timezone="Asia/Seoul")
    scheduler.add_job(check_btc_price_change, 'interval', minutes=5)
    scheduler.start()
