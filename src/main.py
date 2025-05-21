from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from modules.report import generate_profit_report
import os

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("BTC 봇에 오신 걸 환영합니다!")

async def profit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_chat.id) != TELEGRAM_CHAT_ID:
        return
    msg = generate_profit_report()
    await update.message.reply_text(msg)

def run():
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("profit", profit))
    app.run_polling()

if __name__ == "__main__":
    run()