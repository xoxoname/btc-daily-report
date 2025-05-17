# Telegram bot main logic
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Hello! I'm your BTC bot.")

def start_bot():
    app = ApplicationBuilder().token('YOUR_BOT_TOKEN').build()
    app.add_handler(CommandHandler("start", start))
    app.run_polling()