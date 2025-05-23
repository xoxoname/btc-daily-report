import asyncio
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from modules.report import fetch_profit_report

async def profit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    report = await fetch_profit_report()
    await context.bot.send_message(chat_id=update.effective_chat.id, text=report)

def start_bot():
    from os import getenv
    app = ApplicationBuilder().token(getenv("TELEGRAM_BOT_TOKEN")).build()
    app.add_handler(CommandHandler("profit", profit))
    app.run_polling()
