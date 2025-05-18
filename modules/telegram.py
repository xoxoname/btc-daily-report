import os, time
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from modules.report import generate_report

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = int(os.getenv("TELEGRAM_CHAT_ID"))

async def handle_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != CHAT_ID:
        return
    msg = generate_report()
    await context.bot.send_message(chat_id=CHAT_ID, text=msg)

def start_bot():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("report", handle_report))
    app.run_polling()
