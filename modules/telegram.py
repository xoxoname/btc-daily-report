# modules/telegram.py

import os
from telegram.ext import Updater, CommandHandler
from modules.report import generate_report, generate_profit, generate_forecast, generate_schedule

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = int(os.environ.get("TELEGRAM_CHAT_ID"))


def handle_report(update, context):
    if update.effective_chat.id == TELEGRAM_CHAT_ID:
        message = generate_report()
        context.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        
def handle_forecast(update, context):
    if update.effective_chat.id == TELEGRAM_CHAT_ID:
        message = generate_forecast()
        context.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)

def handle_profit(update, context):
    if update.effective_chat.id == TELEGRAM_CHAT_ID:
        message = generate_profit()
        context.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)

def handle_schedule(update, context):
    if update.effective_chat.id == TELEGRAM_CHAT_ID:
        message = generate_schedule()
        context.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)


def start_bot():
    updater = Updater(TELEGRAM_BOT_TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("report", handle_report))
    dp.add_handler(CommandHandler("forecast", handle_forecast))
    dp.add_handler(CommandHandler("profit", handle_profit))
    dp.add_handler(CommandHandler("schedule", handle_schedule))

    updater.start_polling()
    updater.idle()
