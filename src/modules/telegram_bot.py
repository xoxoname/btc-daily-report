from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import os
from modules.report import generate_report

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

async def report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(generate_report())

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📡 BTC 예측 시스템 정상 작동 중입니다. /report, /profit 등을 입력하세요!")

def start_bot():
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("report", report))
    print("✅ 텔레그램 봇이 시작되었습니다.")
    app.run_polling()