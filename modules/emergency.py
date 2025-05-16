import time
from modules.utils import fetch_coinbase_price, send_telegram_message
from modules.constants import EMERGENCY_THRESHOLD_PERCENT
from threading import Thread

def start_emergency_monitor():
    def monitor():
        last_price = fetch_coinbase_price()
        while True:
            time.sleep(300)  # 5분마다
            current_price = fetch_coinbase_price()
            if current_price and last_price:
                change = abs((current_price - last_price) / last_price) * 100
                if change >= EMERGENCY_THRESHOLD_PERCENT:
                    send_telegram_message(
                        f"🚨 *BTC 긴급 변동 감지!*\n"
                        f"💰 현재 BTC 가격: ${current_price:,.2f}\n"
                        f"📉 변화율: {change:.2f}%"
                    )
                    last_price = current_price
    Thread(target=monitor, daemon=True).start()
