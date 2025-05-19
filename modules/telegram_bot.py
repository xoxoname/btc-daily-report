import os
import asyncio
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from modules.reporter import format_profit_report

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = int(os.getenv("TELEGRAM_CHAT_ID"))

async def send_long_message(text, chat_id=CHAT_ID):
    from telegram import Bot
    bot = Bot(token=TOKEN)
    max_length = 4000
    for i in range(0, len(text), max_length):
        await bot.send_message(chat_id=chat_id, text=text[i:i + max_length])

async def profit_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = format_profit_report()
    await send_long_message(msg, chat_id=update.effective_chat.id)

def run_telegram_bot():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("profit", profit_command))
    asyncio.run(app.run_polling())
