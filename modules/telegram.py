
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from modules.constants import TELEGRAM_BOT_TOKEN
from modules.report import generate_report
from modules.schedule import get_schedule

async def report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(generate_report())

async def forecast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔮 Forecast logic placeholder")

async def profit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("💸 Profit report logic placeholder")

async def schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(get_schedule())

def start_bot():
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("report", report))
    app.add_handler(CommandHandler("forecast", forecast))
    app.add_handler(CommandHandler("profit", profit))
    app.add_handler(CommandHandler("schedule", schedule))
    app.run_polling()
