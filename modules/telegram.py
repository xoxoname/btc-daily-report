from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import os
from modules.report import generate_full_report, generate_profit_report, generate_prediction

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = int(os.getenv("TELEGRAM_CHAT_ID"))

async def handle_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    if "/리포트" in text:
        msg = generate_full_report()
    elif "/수익" in text:
        msg = generate_profit_report()
    elif "/예측" in text:
        msg = generate_prediction()
    elif "/일정" in text:
        msg = "📅 향후 7일간 주요 일정 (/일정 명령어 예시)\n- 예시: 트럼프 연설, FOMC 발표 등"
    else:
        msg = "명령어를 인식하지 못했습니다. /리포트, /수익, /예측, /일정 중 하나를 사용하세요."

    await context.bot.send_message(chat_id=update.effective_chat.id, text=msg)

def run_bot():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler(["리포트", "수익", "예측", "일정"], handle_command))

    app.run_polling()
