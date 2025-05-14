import os
import requests
import asyncio
from flask import Flask, jsonify
from telegram import Update, BotCommand
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

# Load from Render environment variables
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
BACKEND_URL = "https://btc-daily-report.onrender.com/report"

app = Flask(__name__)

# ==============================
# 리포트 핸들러 함수 정의
# ==============================
async def handle_profit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("수익 리포트를 생성 중입니다... ⏳")
    try:
        r = requests.get(f"{BACKEND_URL}?type=profit")
        await update.message.reply_text(r.text)
    except Exception as e:
        await update.message.reply_text(f"⚠️ 수익 리포트 오류: {e}")

async def handle_forecast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("12시간 예측 리포트를 생성 중입니다... 🔍")
    try:
        r = requests.get(f"{BACKEND_URL}?type=forecast")
        await update.message.reply_text(r.text)
    except Exception as e:
        await update.message.reply_text(f"⚠️ 예측 리포트 오류: {e}")

async def handle_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("정밀 보고서를 생성 중입니다... 📊")
    try:
        r = requests.get(f"{BACKEND_URL}?type=full")
        await update.message.reply_text(r.text)
    except Exception as e:
        await update.message.reply_text(f"⚠️ 정밀 리포트 오류: {e}")

# ==============================
# 자연어 입력 핸들링
# ==============================
async def handle_natural(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.lower()
    if any(k in text for k in ["수익", "얼마", "포지션"]):
        await handle_profit(update, context)
    elif any(k in text for k in ["예측", "예상", "동향", "방향"]):
        await handle_forecast(update, context)
    elif any(k in text for k in ["정밀", "리포트", "분석"]):
        await handle_report(update, context)
    else:
        await update.message.reply_text("🤖 명령을 인식하지 못했습니다. 예: '수익 보여줘', '예측 리포트 줘' 등으로 입력해주세요.")

# ==============================
# 텔레그램 봇 실행
# ==============================
async def set_commands(app_bot):
    await app_bot.bot.set_my_commands([
        BotCommand("profit", "현재 수익/포지션 리포트 제공"),
        BotCommand("forecast", "12시간 BTC 예측 분석"),
        BotCommand("report", "정밀 종합 리포트 제공")
    ])


def run_telegram_bot():
    app_bot = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app_bot.add_handler(CommandHandler("profit", handle_profit))
    app_bot.add_handler(CommandHandler("forecast", handle_forecast))
    app_bot.add_handler(CommandHandler("report", handle_report))
    app_bot.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_natural))

    asyncio.run(set_commands(app_bot))
    app_bot.run_polling()

# ==============================
# Flask 엔드포인트
# ==============================
@app.route("/")
def home():
    return "BTC Telegram Bot Running"

@app.route("/report")
def report():
    try:
        return requests.get(BACKEND_URL).text
    except Exception as e:
        return f"/report 호출 오류: {e}", 500

if __name__ == "__main__":
    import threading
    threading.Thread(target=run_telegram_bot).start()
    app.run(host="0.0.0.0", port=10000)
