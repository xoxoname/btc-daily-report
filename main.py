from flask import Flask, jsonify
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler,
    MessageHandler, ContextTypes, filters
)
from modules.report import (
    get_profit_report, get_prediction_report,
    get_full_prediction_report
)
import threading
import asyncio

app = Flask(__name__)

TELEGRAM_TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"
application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

# 텔레그램 핸들러들
async def handle_profit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = get_profit_report()
    await update.message.reply_text(text)

async def handle_predict(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = get_prediction_report()
    await update.message.reply_text(text)

async def handle_full_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = get_full_prediction_report()
    await update.message.reply_text(text)

async def handle_text_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message.text.lower()
    if "수익" in message:
        await handle_profit(update, context)
    elif "예측" in message:
        await handle_predict(update, context)
    elif "리포트" in message or "분석" in message:
        await handle_full_report(update, context)
    else:
        await update.message.reply_text("❓ 요청을 인식하지 못했습니다. 예: 수익, 예측, 리포트")

application.add_handler(CommandHandler("profit", handle_profit))
application.add_handler(CommandHandler("predict", handle_predict))
application.add_handler(CommandHandler("report", handle_full_report))
application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_text_query))

# 🔧 Flask 엔드포인트
@app.route("/")
def index():
    return "✅ BTC 리포트 시스템 정상 작동 중입니다."

@app.route("/report")
def report_api():
    return jsonify({
        "usdt_pnl": "+187.2",
        "krw_pnl": "252,000"
    })

# 🔁 비동기 텔레그램 봇 루프 (렌더 비동기 환경 대응)
def run_bot():
    asyncio.set_event_loop(asyncio.new_event_loop())
    application.run_polling()

if __name__ == "__main__":
    threading.Thread(target=run_bot).start()
    app.run(host="0.0.0.0", port=10000)
