
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from modules.reports import generate_report, generate_profit, generate_forecast, generate_schedule
from modules.constants import BOT_TOKEN

async def report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = generate_report()
    await update.message.reply_text(message)

async def profit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = generate_profit()
    await update.message.reply_text(message)

async def forecast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = generate_forecast()
    await update.message.reply_text(message)

async def schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = generate_schedule()
    await update.message.reply_text(message)

def start_bot():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("report", report))
    app.add_handler(CommandHandler("profit", profit))
    app.add_handler(CommandHandler("forecast", forecast))
    app.add_handler(CommandHandler("schedule", schedule))
    app.run_polling()
