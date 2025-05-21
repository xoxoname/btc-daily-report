from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import os
from modules.bitget_api import test_bitget

def get_env(key):
    v = os.environ.get(key, '').strip()
    print(f"[telegram_bot] ENV {key} = [{v}]")
    return v

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("안녕하세요! BTC 리포트 봇입니다.")

async def profit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    allowed_id = get_env("TELEGRAM_CHAT_ID")
    if chat_id != allowed_id:
        await update.message.reply_text("❗️권한이 없습니다.")
        return
    res = test_bitget()
    msg = f"❗️비트겟 API 오류: {res.get('msg', res)}" if res.get("code") != "00000" else f"계좌조회 성공: {res}"
    await update.message.reply_text(msg)

def start_bot():
    token = get_env("TELEGRAM_BOT_TOKEN")
    print(f"[telegram_bot] TELEGRAM_BOT_TOKEN = [{token}]")
    app = ApplicationBuilder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("profit", profit))
    print("[telegram_bot] Bot polling start!")
    app.run_polling()
