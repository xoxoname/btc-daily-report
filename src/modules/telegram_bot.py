from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import os
from modules.report import generate_report
from modules.profit import generate_profit_report

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

async def report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print(f"📩 /report 호출 - 사용자: {update.effective_user.id}")
    await update.message.reply_text(generate_report())

async def profit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print(f"📩 /profit 호출 - 사용자: {update.effective_user.id}")
    await update.message.reply_text(generate_profit_report())

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print(f"📩 /start 호출 - 사용자: {update.effective_user.id}")
    await update.message.reply_text("📡 BTC 예측 시스템 정상 작동 중입니다. /report, /profit 등을 입력하세요!")

def start_bot():
    print("🟢 텔레그램 봇 초기화 중...")
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("report", report))
    app.add_handler(CommandHandler("profit", profit))
    print("✅ 텔레그램 봇이 시작되었습니다.")
    app.run_polling()