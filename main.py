import os
import time
import requests
from flask import Flask
from dotenv import load_dotenv
from apscheduler.schedulers.background import BackgroundScheduler
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from report_generator import generate_report, generate_forecast

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

app = Flask(__name__)

# Telegram bot setup
tg_app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

# /profit 명령어 처리
async def handle_profit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = generate_report()
    await update.message.reply_text(text)

# /forecast 명령어 처리
async def handle_forecast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = generate_forecast()
    await update.message.reply_text(text)

tg_app.add_handler(CommandHandler("profit", handle_profit))
tg_app.add_handler(CommandHandler("forecast", handle_forecast))

# 정기 리포트 전송 스케줄러
scheduler = BackgroundScheduler(timezone="Asia/Seoul")

def send_forecast_report():
    try:
        text = generate_forecast()
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": text
        }
        requests.post(url, json=payload)
    except Exception as e:
        print(f"[예측 전송 실패] {e}")

# 09:30, 13:00, 23:00 (한국시간) 정규 예측 리포트 전송
scheduler.add_job(send_forecast_report, "cron", hour=9, minute=30)
scheduler.add_job(send_forecast_report, "cron", hour=13, minute=0)
scheduler.add_job(send_forecast_report, "cron", hour=23, minute=0)
scheduler.start()

# Flask 포트 대기 (Render Web Service 요구사항)
@app.route('/')
def health_check():
    return "BTC Report Web Service is running!"

if __name__ == "__main__":
    import threading

    # 텔레그램 봇은 백그라운드 스레드로 실행
    def run_tg_bot():
        tg_app.run_polling()

    tg_thread = threading.Thread(target=run_tg_bot)
    tg_thread.start()

    # Flask는 포트 열어서 Render가 살아있다고 판단하게 함
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
