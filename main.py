from flask import Flask, jsonify
from apscheduler.schedulers.background import BackgroundScheduler
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from report import get_profit_report, get_prediction_report
import threading
import asyncio
import os

app = Flask(__name__)

# Flask 엔드포인트
@app.route("/")
def home():
    return "BTC 자동 리포트 서비스입니다."

@app.route("/report")
def report():
    return jsonify(get_profit_report())

# Telegram 핸들러
async def handle_profit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = get_profit_report()
    msg = f"💰 실시간 수익:\nUSDT 기준: {result['usdt_pnl']} USDT\nKRW 기준: {result['krw_pnl']} 원"
    await update.message.reply_text(msg)

async def handle_prediction(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = get_prediction_report()
    await update.message.reply_text(result)

def run_bot():
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    application = ApplicationBuilder().token(token).build()
    application.add_handler(CommandHandler("수익", handle_profit))
    application.add_handler(CommandHandler("예측", handle_prediction))

    # asyncio 오류 방지
    asyncio.run(application.run_polling())

if __name__ == "__main__":
    # 텔레그램 봇은 별도 쓰레드로 실행
    threading.Thread(target=run_bot).start()

    # Flask 앱 실행
    app.run(host="0.0.0.0", port=10000)
