import os
from telegram.ext import Updater, CommandHandler
from modules.report import generate_report, generate_profit, generate_forecast, generate_schedule

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def start_bot():
    updater = Updater(token=TELEGRAM_TOKEN, use_context=True)
    dispatcher = updater.dispatcher

    dispatcher.add_handler(CommandHandler("report", handle_report))
    dispatcher.add_handler(CommandHandler("forecast", handle_forecast))
    dispatcher.add_handler(CommandHandler("profit", handle_profit))
    dispatcher.add_handler(CommandHandler("schedule", handle_schedule))

    updater.start_polling()
    updater.idle()

def handle_report(update, context):
    text = generate_report()
    context.bot.send_message(chat_id=update.effective_chat.id, text=text)

def handle_forecast(update, context):
    text = generate_forecast()
    context.bot.send_message(chat_id=update.effective_chat.id, text=text)

def handle_profit(update, context):
    text = generate_profit()
    context.bot.send_message(chat_id=update.effective_chat.id, text=text)

def handle_schedule(update, context):
    text = generate_schedule()
    context.bot.send_message(chat_id=update.effective_chat.id, text=text)
