
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from modules.constants import BOT_TOKEN
from modules.report import generate_full_report
from modules.forecast import generate_forecast_report
from modules.profit import generate_profit_report
from modules.schedule import generate_schedule_report

async def report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(await generate_full_report())

async def forecast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(await generate_forecast_report())

async def profit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(await generate_profit_report())

async def schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(await generate_schedule_report())

def start_bot():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("report", report))
    app.add_handler(CommandHandler("forecast", forecast))
    app.add_handler(CommandHandler("profit", profit))
    app.add_handler(CommandHandler("schedule", schedule))
    app.run_polling()
