import os
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters
from modules.reporter import format_report, format_forecast, format_profit
from modules.exchange import get_position_info

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN") or "YOUR_TELEGRAM_BOT_TOKEN"

async def report_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(format_report())

async def forecast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(format_forecast())

async def profit_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(format_profit(get_position_info()))

async def schedule_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from modules.analyst import gpt_event_scan
    await update.message.reply_text("📅 자동 일정\n\n" + gpt_event_scan())

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.lower()
    if "수익" in txt:
        await profit_command(update, context)
    elif "매수" in txt or "매도" in txt or "예측" in txt:
        await forecast_command(update, context)
    elif "일정" in txt or "이벤트" in txt:
        await schedule_command(update, context)
    else:
        await update.message.reply_text("지원 명령: /report, /forecast, /profit, /schedule")

def start_telegram_bot():
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("report", report_command))
    app.add_handler(CommandHandler("forecast", forecast_command))
    app.add_handler(CommandHandler("profit", profit_command))
    app.add_handler(CommandHandler("schedule", schedule_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    app.run_polling()
