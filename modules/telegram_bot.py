import os
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters
from modules.reporter import format_report, format_forecast, format_profit
from modules.exchange import get_position_info

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]

# 긴 메시지 자동 분할(4096자 이하) 유틸리티
async def safe_reply(update, text):
    MAX_LEN = 4096
    for i in range(0, len(text), MAX_LEN):
        await update.message.reply_text(text[i:i+MAX_LEN])

async def report_command(update, context):
    await safe_reply(update, format_report())

async def forecast_command(update, context):
    await safe_reply(update, format_forecast())

async def profit_command(update, context):
    await safe_reply(update, format_profit(get_position_info()))

async def schedule_command(update, context):
    from modules.analyst import gpt_event_scan
    await safe_reply(update, "📅 자동 일정\n\n" + gpt_event_scan())

async def text_handler(update, context):
    txt = update.message.text.lower()
    if "수익" in txt:
        await profit_command(update, context)
    elif "매수" in txt or "매도" in txt or "예측" in txt:
        await forecast_command(update, context)
    elif "일정" in txt or "이벤트" in txt:
        await schedule_command(update, context)
    else:
        await safe_reply(update, "지원 명령: /report, /forecast, /profit, /schedule")

def run_telegram_bot():
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("report", report_command))
    app.add_handler(CommandHandler("forecast", forecast_command))
    app.add_handler(CommandHandler("profit", profit_command))
    app.add_handler(CommandHandler("schedule", schedule_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    app.run_polling()
