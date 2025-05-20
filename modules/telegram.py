import os
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from modules.bitget import get_position
from modules.report import format_profit_report

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
ALLOWED_CHAT_ID = int(os.environ.get("TELEGRAM_CHAT_ID", "0"))
BITGET_APIKEY = os.environ.get("BITGET_APIKEY")
BITGET_APISECRET = os.environ.get("BITGET_APISECRET")
BITGET_PASSPHRASE = os.environ.get("BITGET_PASSPHRASE")

async def profit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != ALLOWED_CHAT_ID:
        await update.message.reply_text("❌ 접근 권한이 없습니다.")
        return
    try:
        position = get_position(BITGET_APIKEY, BITGET_APISECRET, BITGET_PASSPHRASE)
        msg = format_profit_report(position)
    except Exception as e:
        msg = f"수익 정보 조회 오류: {e}"
    await update.message.reply_text(msg)

def run_telegram_bot():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("profit", profit))
    app.run_polling()
