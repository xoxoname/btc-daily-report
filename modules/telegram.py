
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from modules.report import generate_report
from modules.schedule import get_schedule
from modules.constants import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

async def report_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(generate_report())

async def schedule_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(get_schedule())

def start_bot():
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("report", report_command))
    app.add_handler(CommandHandler("schedule", schedule_command))
    app.add_handler(CommandHandler("forecast", report_command))
    app.run_polling()
