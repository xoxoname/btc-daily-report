import os
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from telegram import Update
from modules.reporter import format_profit_report

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = int(os.environ.get("TELEGRAM_CHAT_ID", "0"))

async def profit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != TELEGRAM_CHAT_ID:
        await update.message.reply_text("접근 권한 없음.")
        return
    report = format_profit_report()
    await update.message.reply_text(report)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != TELEGRAM_CHAT_ID:
        await update.message.reply_text("접근 권한 없음.")
        return
    await update.message.reply_text("BTC 데일리 리포트 봇입니다. /profit 입력!")

async def run_telegram_bot():
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("profit", profit))
    await app.run_polling()
