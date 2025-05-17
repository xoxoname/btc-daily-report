import os
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from modules.report import get_formatted_report

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
AUTHORIZED_CHAT_ID = "1038440081"  # 사용자의 Chat ID

# 명령어 응답 핸들러
async def report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_chat.id) != AUTHORIZED_CHAT_ID:
        return
    await update.message.reply_text(get_formatted_report())

# 명령어 등록 및 봇 실행
def start_bot():
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("report", report))
    app.run_polling()
