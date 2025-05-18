from telegram import Update, BotCommand
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from modules.handlers import handle_report, handle_forecast, handle_profit, handle_schedule
import os

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🤖 BTC 분석 봇이 작동 중입니다. /report, /forecast, /profit, /schedule 명령어를 사용해보세요!")

async def start_telegram_bot():
    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("report", handle_report))
    application.add_handler(CommandHandler("forecast", handle_forecast))
    application.add_handler(CommandHandler("profit", handle_profit))
    application.add_handler(CommandHandler("schedule", handle_schedule))

    await application.bot.set_my_commands([
        BotCommand("report", "📡 GPT 분석 리포트"),
        BotCommand("forecast", "🔮 단기 매동 예측"),
        BotCommand("profit", "📈 수익 현황 보기"),
        BotCommand("schedule", "📆 발송 일정 확인")
    ])

    print("Telegram 봇이 시작되었습니다.")
    await application.run_polling()
