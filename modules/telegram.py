from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from .reporter import generate_report
from .constants import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_chat.id) != str(TELEGRAM_CHAT_ID):
        await update.message.reply_text("❌ 인증된 사용자만 사용 가능합니다.")
        return
    text = update.message.text.strip()
    if text in ["/리포트", "/report", "/예측", "/forecast", "/수익", "/profit"]:
        await update.message.reply_text("⏳ 분석 중입니다. 잠시만 기다려주세요...")
        try:
            report = generate_report()
            await update.message.reply_text(report)
        except Exception as e:
            await update.message.reply_text(f"❗️리포트 생성 오류: {e}")

def run_telegram_bot():
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    app.add_handler(CommandHandler("리포트", handle_message))
    app.add_handler(CommandHandler("report", handle_message))
    app.add_handler(CommandHandler("예측", handle_message))
    app.add_handler(CommandHandler("forecast", handle_message))
    app.add_handler(CommandHandler("수익", handle_message))
    app.add_handler(CommandHandler("profit", handle_message))
    app.run_polling()
