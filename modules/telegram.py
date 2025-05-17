import os
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from modules.report import generate_profit_report

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ALLOWED_CHAT_ID = "1038440081"  # Only allow this user


def check_authorized(update: Update):
    return str(update.effective_chat.id) == ALLOWED_CHAT_ID


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not check_authorized(update):
        return
    await update.message.reply_text("✅ BTC 리포트 봇에 오신 걸 환영합니다! 명령어: /report /profit /forecast /schedule")


async def profit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not check_authorized(update):
        return
    msg = generate_profit_report()
    await update.message.reply_text(msg)


async def report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not check_authorized(update):
        return
    await update.message.reply_text("📡 전체 리포트는 준비 중입니다.")


async def forecast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not check_authorized(update):
        return
    await update.message.reply_text("📡 예측 분석은 준비 중입니다.")


async def schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not check_authorized(update):
        return
    msg = (
        "📅 향후 7일간 주요 일정 (/schedule 명령어 예시)\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "📌 5/18 (토) 21:30 — FOMC 의사록 공개\n"
        "📌 5/20 (월) 09:00 — 🇰🇷 수출입지수 발표\n"
        "📌 5/22 (수) 03:00 — 🇺🇸 파월 의장 발언 예정\n"
        "📌 5/23 (목) 21:30 — 🇺🇸 신규 실업수당 청구건수\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "📍 GPT 분석 기준: 시장 영향도 높은 일정만 선별"
    )
    await update.message.reply_text(msg)


def run_bot():
    if not TELEGRAM_TOKEN:
        raise Exception("TELEGRAM_BOT_TOKEN 환경변수가 필요합니다.")

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("profit", profit))
    app.add_handler(CommandHandler("report", report))
    app.add_handler(CommandHandler("forecast", forecast))
    app.add_handler(CommandHandler("schedule", schedule))

    print("✅ Telegram Bot started with polling...")
    app.run_polling()
