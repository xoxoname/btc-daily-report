# modules/telegram.py
import asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from modules.report import generate_report, generate_profit, generate_forecast, generate_schedule
import os

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID = int(os.environ.get("TELEGRAM_CHAT_ID"))

async def report_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != CHAT_ID:
        return
    message = await generate_report()
    await context.bot.send_message(chat_id=update.effective_chat.id, text=message)

async def profit_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != CHAT_ID:
        return
    message = await generate_profit()
    await context.bot.send_message(chat_id=update.effective_chat.id, text=message)

async def forecast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != CHAT_ID:
        return
    message = await generate_forecast()
    await context.bot.send_message(chat_id=update.effective_chat.id, text=message)

async def schedule_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != CHAT_ID:
        return
    message = await generate_schedule()
    await context.bot.send_message(chat_id=update.effective_chat.id, text=message)

def start_bot():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("report", report_command))
    app.add_handler(CommandHandler("profit", profit_command))
    app.add_handler(CommandHandler("forecast", forecast_command))
    app.add_handler(CommandHandler("schedule", schedule_command))
    app.run_polling()
