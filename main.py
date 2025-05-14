# main.py

from flask import Flask
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler,
    MessageHandler, ContextTypes, filters
)
from modules.report import (
    get_profit_report, get_prediction_report,
    get_full_prediction_report
)

app = Flask(__name__)

TELEGRAM_TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"
application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

# /profit
async def handle_profit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = get_profit_report()
    await update.message.reply_text(text)

# /predict
async def handle_predict(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = get_prediction_report()
    await update.message.reply_text(text)

# /report
async def handle_full_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = get_full_prediction_report()
    await update.message.reply_text(text)

# 자연어 핸들러
async def handle_text_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message.text.lower()
    if "수익" in message:
        await handle_profit(update, context)
    elif "예측" in message:
        await handle_predict(update, context)
    elif "리포트" in message or "분석" in message:
        await handle_full_report(update, context)
    else:
        await update.message.reply_text("❓ 무슨 요청인지 정확히 알려주세요. 예: 수익, 예측, 리포트")

# 명령어 등록
application.add_handler(CommandHandler("profit", handle_profit))
application.add_handler(CommandHandler("predict", handle_predict))
application.add_handler(CommandHandler("report", handle_full_report))
application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_text_query))

# 웹 루트
@app.route("/")
def index():
    return "BTC 리포트 서비스 정상 작동 중"

# 실행
if __name__ == "__main__":
    import threading

    def run_bot():
        application.run_polling()

    threading.Thread(target=run_bot).start()
    app.run(host="0.0.0.0", port=10000)
