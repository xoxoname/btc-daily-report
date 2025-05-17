import os
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from modules.schedule import generate_schedule

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

async def handle_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    command = update.message.text.strip().lower()
    if command == "/schedule":
        msg = generate_schedule()
        await context.bot.send_message(chat_id=update.effective_chat.id, text=msg)
    elif command == "/profit":
        await context.bot.send_message(chat_id=update.effective_chat.id, text="❌ 수익 정보 조회 실패: API fetch failed.")
    elif command == "/forecast":
        await context.bot.send_message(chat_id=update.effective_chat.id, text="📡 예측 분석은 준비 중입니다.")
    elif command == "/report":
        await context.bot.send_message(chat_id=update.effective_chat.id, text="📡 전체 리포트는 준비 중입니다.")
    else:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="알 수 없는 명령어입니다.")

def run_bot():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler(["schedule", "profit", "forecast", "report"], handle_command))
    app.run_polling()