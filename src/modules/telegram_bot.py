
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import os
from modules.report import generate_report
from modules.profit import generate_profit_report

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ 봇이 정상적으로 작동 중입니다. /report 또는 /profit을 입력해보세요.")

async def report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(generate_report())

async def profit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(generate_profit_report())

def start_bot():
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("report", report))
    app.add_handler(CommandHandler("profit", profit))
    app.run_polling()
