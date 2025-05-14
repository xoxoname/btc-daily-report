from flask import Flask
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
from apscheduler.schedulers.background import BackgroundScheduler
from modules.report import get_profit_report, get_prediction_report, get_full_prediction_report
import logging
import os

# Telegram 토큰 및 사용자 ID
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

# 기본 앱 설정
app = Flask(__name__)
scheduler = BackgroundScheduler()
bot_app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

# 1️⃣ 핸들러 함수 정의
async def handle_profit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(get_profit_report())

async def handle_prediction(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(get_prediction_report())

async def handle_full_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(get_full_prediction_report())

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.lower()
    if "수익" in text or "profit" in text:
        await handle_profit(update, context)
    elif "예측" in text or "report" in text or "리포트" in text:
        await handle_full_report(update, context)
    else:
        await update.message.reply_text("원하시는 명령어를 인식하지 못했어요. '수익', '예측', '리포트' 등을 말씀해주세요.")

# 2️⃣ 정기 자동 알림 전송
def send_scheduled_report():
    try:
        report = get_full_prediction_report()
        bot_app.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=report)
    except Exception as e:
        print(f"자동 전송 오류: {e}")

# 3️⃣ 스케줄 등록 (UTC 기준 → KST 기준: 00:30, 04:00, 14:00)
scheduler.add_job(send_scheduled_report, 'cron', hour=0, minute=30)
scheduler.add_job(send_scheduled_report, 'cron', hour=4, minute=0)
scheduler.add_job(send_scheduled_report, 'cron', hour=14, minute=0)
scheduler.start()

# 4️⃣ 핸들러 등록
bot_app.add_handler(CommandHandler("수익", handle_profit))
bot_app.add_handler(CommandHandler("profit", handle_profit))
bot_app.add_handler(CommandHandler("예측", handle_prediction))
bot_app.add_handler(CommandHandler("report", handle_full_report))
bot_app.add_handler(CommandHandler("리포트", handle_full_report))
bot_app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_text))

# 5️⃣ 실행
def run_telegram():
    bot_app.run_polling()

import threading
threading.Thread(target=run_telegram).start()

@app.route('/')
def home():
    return "BTC 리포트 서버 정상 작동 중"

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=10000)
