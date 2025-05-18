from telegram.ext import Updater, CommandHandler
from modules.constants import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
from modules.report import generate_report, generate_forecast, generate_schedule
from modules.profit import generate_profit

def handle_report(update, context):
    if update.effective_chat.id == TELEGRAM_CHAT_ID:
        context.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=generate_report())

def handle_forecast(update, context):
    if update.effective_chat.id == TELEGRAM_CHAT_ID:
        context.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=generate_forecast())

def handle_profit(update, context):
    if update.effective_chat.id == TELEGRAM_CHAT_ID:
        context.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=generate_profit())

def handle_schedule(update, context):
    if update.effective_chat.id == TELEGRAM_CHAT_ID:
        context.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=generate_schedule())

def start_bot():
    updater = Updater(TELEGRAM_BOT_TOKEN, use_context=True)
    dp = updater.dispatcher
    dp.add_handler(CommandHandler("report", handle_report))
    dp.add_handler(CommandHandler("forecast", handle_forecast))
    dp.add_handler(CommandHandler("profit", handle_profit))
    dp.add_handler(CommandHandler("schedule", handle_schedule))
    updater.start_polling()
    updater.idle()
