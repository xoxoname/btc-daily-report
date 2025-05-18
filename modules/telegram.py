from telegram.ext import Updater, CommandHandler
from modules.constants import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
from modules.report import generate_report, generate_profit, generate_forecast, generate_schedule

def start(update, context):
    context.bot.send_message(chat_id=update.effective_chat.id, text="BTC 리포트 시스템 작동 중입니다.")

def report(update, context):
    context.bot.send_message(chat_id=update.effective_chat.id, text=generate_report())

def profit(update, context):
    context.bot.send_message(chat_id=update.effective_chat.id, text=generate_profit())

def forecast(update, context):
    context.bot.send_message(chat_id=update.effective_chat.id, text=generate_forecast())

def schedule(update, context):
    context.bot.send_message(chat_id=update.effective_chat.id, text=generate_schedule())

def start_bot():
    updater = Updater(token=TELEGRAM_BOT_TOKEN, use_context=True)
    dp = updater.dispatcher
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("report", report))
    dp.add_handler(CommandHandler("profit", profit))
    dp.add_handler(CommandHandler("forecast", forecast))
    dp.add_handler(CommandHandler("schedule", schedule))
    updater.start_polling()
    updater.idle()
