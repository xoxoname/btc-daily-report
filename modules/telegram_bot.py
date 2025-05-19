import os
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from telegram import Update
from .reporter import format_profit_report

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID = int(os.environ.get("TELEGRAM_CHAT_ID"))

async def profit_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != CHAT_ID:
        await update.message.reply_text("인증된 사용자만 사용 가능합니다.")
        return
    msg = format_profit_report()
    # 메시지 길이 제한 대비
    for i in range(0, len(msg), 4096):
        await update.message.reply_text(msg[i:i+4096])

def run_telegram_bot():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("profit", profit_command))
    app.run_polling()
