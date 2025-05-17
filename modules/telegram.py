from telegram.ext import ApplicationBuilder, CommandHandler
from modules.constants import TELEGRAM_BOT_TOKEN

async def start(update, context):
    await update.message.reply_text('Bot started.')

def start_bot():
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler('start', start))
    app.run_polling()
