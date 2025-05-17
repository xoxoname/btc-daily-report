from telegram.ext import ApplicationBuilder, CommandHandler
from modules.constants import TELEGRAM_BOT_TOKEN
from modules.report import send_forecast_report, send_profit_report, send_schedule_report, send_regular_report

def start_bot():
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("예측", send_forecast_report))
    app.add_handler(CommandHandler("수익", send_profit_report))
    app.add_handler(CommandHandler("일정", send_schedule_report))
    app.add_handler(CommandHandler("리포트", send_regular_report))

    app.run_polling()
