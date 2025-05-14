import os
import time
import asyncio
import logging
from flask import Flask
from telegram import Update, BotCommand
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

from modules.report import get_profit_report, get_prediction_report, get_full_prediction_report

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")

app = Flask(__name__)

# ✅ /report HTTP 라우트 추가
@app.route("/report", methods=["GET"])
def http_report():
    try:
        report = asyncio.run(get_full_prediction_report())
        return report, 200
    except Exception as e:
        return f"Error generating report: {str(e)}", 500

# 📲 텔레그램 핸들러
async def handle_profit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = await get_profit_report()
    await update.message.reply_text(result)

async def handle_prediction(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = await get_prediction_report()
    await update.message.reply_text(result)

async def handle_full_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = await get_full_prediction_report()
    await update.message.reply_text(result)

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.lower()
    if "수익" in text or "profit" in text:
        await handle_profit(update, context)
    elif "예측" in text or "prediction" in text:
        await handle_prediction(update, context)
    elif "리포트" in text or "report" in text:
        await handle_full_report(update, context)
    else:
        await update.message.reply_text("명령어를 인식하지 못했습니다. 예: /수익 또는 '수익 알려줘'")

async def set_bot_commands(application):
    await application.bot.set_my_commands([
        BotCommand("수익", "현재 수익 정보 확인"),
        BotCommand("예측", "예상 매매 동향 요약"),
        BotCommand("리포트", "전체 정밀 리포트 수신"),
    ])

async def run_telegram_bot():
    application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    application.add_handler(CommandHandler(["수익", "profit"], handle_profit))
    application.add_handler(CommandHandler(["예측", "prediction"], handle_prediction))
    application.add_handler(CommandHandler(["리포트", "report"], handle_full_report))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_text))

    await set_bot_commands(application)
    await application.initialize()
    await application.start()
    await application.updater.start_polling()
    await application.updater.idle()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    port = int(os.environ.get("PORT", 10000))
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.create_task(run_telegram_bot())
    app.run(host="0.0.0.0", port=port)
