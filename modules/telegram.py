from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from modules.reporter import generate_profit_report

TELEGRAM_BOT_TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"

async def profit_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = generate_profit_report()
    await update.message.reply_text(message)

def start_telegram_bot():
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("profit", profit_command))
    app.run_polling()
