import requests
import time
from threading import Thread

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

last_price = None

def check_btc_price_change():
    global last_price
    try:
        # ✅ 테스트용 강제 푸시 메시지 (조건 없이 무조건 전송됨)
        message = (
            f"📛 *BTC 긴급 변동 감지 테스트!*\n"
            f"💰 현재 BTC 가격: $99,999.99\n"
            f"📉 변화율: 3.00%"
        )
        requests.get(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            params={"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}
        )
        print("[긴급 알림 테스트] 전송 완료")
    except Exception as e:
        print(f"[긴급 감지 에러]: {e}")

def start_emergency_monitor():
    def monitor():
        while True:
            check_btc_price_change()
            time.sleep(300)  # 5분 간격

    Thread(target=monitor, daemon=True).start()
