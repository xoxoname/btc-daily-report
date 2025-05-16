import pytz
from apscheduler.schedulers.background import BackgroundScheduler
from modules.utils import fetch_coinbase_price
from modules.constants import TELEGRAM_CHAT_ID, TELEGRAM_TOKEN, PRICE_CHANGE_THRESHOLD, TIMEZONE
import telegram
from datetime import datetime

last_price = None
scheduler = BackgroundScheduler(timezone=pytz.timezone(TIMEZONE))
bot = telegram.Bot(token=TELEGRAM_TOKEN)

def check_btc_price_change():
    global last_price
    current_price = fetch_coinbase_price()
    if current_price is None:
        return

    if last_price is not None:
        change_percent = abs((current_price - last_price) / last_price) * 100
        if change_percent >= PRICE_CHANGE_THRESHOLD:
            now = datetime.now().strftime("%Y-%m-%d %H:%M")
            message = (
                f"🚨 *BTC 가격 급변동 감지!*\n"
                f"💰 현재 BTC 가격: ${current_price:,.2f}\n"
                f"📉 변화율: {change_percent:.2f}%\n"
                f"🕒 시각: {now} (KST)"
            )
            bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message, parse_mode="Markdown")

    last_price = current_price

def start_emergency_monitor():
    scheduler.add_job(check_btc_price_change, "interval", minutes=5)
    scheduler.start()
