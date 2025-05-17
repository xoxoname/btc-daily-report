from telegram import Update, BotCommand
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import os

from modules.report import generate_full_report, generate_profit_report, generate_prediction
from modules.schedule import generate_schedule

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")

async def handle_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    command = update.message.text.strip()

    if command == "/수익":
        msg = await generate_profit_report()
    elif command == "/예측":
        msg = await generate_prediction()
    elif command == "/리포트":
        msg = await generate_full_report()
    elif command == "/일정":
        msg = await generate_schedule()
    else:
        msg = "알 수 없는 명령어입니다. /수익 /예측 /리포트 /일정 중 하나를 사용하세요."

    await context.bot.send_message(chat_id=update.effective_chat.id, text=msg)

async def set_commands(app):
    await app.bot.set_my_commands([
        BotCommand("수익", "실시간 수익 리포트"),
        BotCommand("예측", "12시간 BTC 예측 분석"),
        BotCommand("리포트", "GPT 심층 리포트"),
        BotCommand("일정", "향후 주요 일정 보기"),
    ])

def run_bot():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("수익", handle_command))
    app.add_handler(CommandHandler("예측", handle_command))
    app.add_handler(CommandHandler("리포트", handle_command))
    app.add_handler(CommandHandler("일정", handle_command))

    app.post_init = set_commands  # 명령어 자동 등록

    app.run_polling()
