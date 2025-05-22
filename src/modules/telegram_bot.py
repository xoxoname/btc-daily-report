from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import os
from modules.report import generate_report
from modules.profit import generate_profit_report

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

async def report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        print(f"[LOG] /report 명령 호출됨 - 사용자 ID: {update.effective_user.id}")
        await update.message.reply_text(generate_report())
    except Exception as e:
        print(f"[ERROR] /report 처리 중 오류: {e}")
        await update.message.reply_text("❗ 리포트 생성 중 오류가 발생했습니다.")

async def profit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        print(f"[LOG] /profit 명령 호출됨 - 사용자 ID: {update.effective_user.id}")
        await update.message.reply_text(generate_profit_report())
    except Exception as e:
        print(f"[ERROR] /profit 처리 중 오류: {e}")
        await update.message.reply_text("❗ 수익 정보 생성 중 오류가 발생했습니다.")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        print(f"[LOG] /start 명령 호출됨 - 사용자 ID: {update.effective_user.id}")
        await update.message.reply_text("✅ 봇 정상 작동 중입니다. /report 또는 /profit 명령어를 입력해보세요!")
    except Exception as e:
        print(f"[ERROR] /start 처리 중 오류: {e}")

def start_bot():
    print("🟢 텔레그램 봇 초기화 중...")
    try:
        app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("report", report))
        app.add_handler(CommandHandler("profit", profit))
        print("✅ 텔레그램 봇이 시작되었습니다.")
        app.run_polling()
    except Exception as e:
        print(f"[ERROR] 텔레그램 봇 실행 중 오류: {e}")