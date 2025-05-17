import os
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from modules.report import generate_full_report, generate_profit_report, generate_prediction

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🤖 BTC 리포트 봇이 준비됐습니다.")


async def report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = generate_full_report()
    await update.message.reply_text(msg)


async def profit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = generate_profit_report()
    await update.message.reply_text(msg)


async def forecast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = generate_prediction()
    await update.message.reply_text(msg)


async def schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "📅 향후 7일간 주요 일정 (/일정 명령어 예시)
"
        "━━━━━━━━━━━━━━━━━━━━
"
        "📌 5/18 (토) 21:30 — FOMC 의사록 공개
"
        "📌 5/20 (월) 09:00 — 🇰🇷 수출입지수 발표
"
        "📌 5/22 (수) 03:00 — 🇺🇸 파월 의장 발언 예정
"
        "📌 5/23 (목) 21:30 — 🇺🇸 신규 실업수당 청구건수
"
        "━━━━━━━━━━━━━━━━━━━━
"
        "📍 GPT 분석 기준: 시장 영향도 높은 일정만 선별"
    )
    await update.message.reply_text(msg)


def run_bot():
    if not TELEGRAM_TOKEN:
        raise Exception("TELEGRAM_BOT_TOKEN 환경변수가 필요합니다.")

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("리포트", report))
    app.add_handler(CommandHandler("수익", profit))
    app.add_handler(CommandHandler("예측", forecast))
    app.add_handler(CommandHandler("일정", schedule))

    print("✅ Telegram Bot started with polling...")
    app.run_polling()
