import os
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

async def handle_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    command = update.message.text.strip().lower()
    if command == "/일정":
        msg = (
            "📅 향후 7일간 주요 일정 (/일정 명령어 예시)\n"
            "날짜 (KST)\t이벤트\t예상 영향\n"
            "5월 17일\t트럼프 대통령 연설\t시장에 긍정적\n"
            "5월 20일\t연준 금리 결정 발표\t변동성 증가\n"
            "5월 22일\t미중 무역 협상 회담\t시장 안정성 영향\n"
            "5월 25일\tBTC 국제 컨퍼런스\t시장 관심도 증가\n"
        )
        await context.bot.send_message(chat_id=update.effective_chat.id, text=msg)

def run_bot():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("일정", handle_command))
    app.run_polling()
