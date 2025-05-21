from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
from modules.constants import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
from modules.report import build_report
from modules.utils import kr_now_str
from modules.bitget_api import get_profit_summary

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_chat.id, text="비트코인 예측 봇에 오신 것을 환영합니다!")

async def handle_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        msg = build_report(
            market_data={}, tech_data={}, psych_data={}, forecast={},
            alerts={}, prev_check={}, pnl={}, user_prompt=""
        )
        await context.bot.send_message(chat_id=update.effective_chat.id, text=msg)
    except Exception as e:
        await context.bot.send_message(chat_id=update.effective_chat.id, text=f"❗️리포트 생성 오류: {e}")

async def handle_profit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    profit = get_profit_summary()
    if "error" in profit:
        await context.bot.send_message(chat_id=update.effective_chat.id, text=f"❗️비트겟 API 오류: {profit['error']}")
        return
    msg = (
        f"💰 현재 수익 현황 요약\n"
        f"📅 작성 시각: {kr_now_str()}\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"📌 포지션 정보\n"
        f"- 종목: {profit['종목']}\n"
        f"- 방향: {profit['방향']}\n"
        f"- 진입가: {profit['진입가']} / 현재가: {profit['현재가']}\n"
        f"- 레버리지: {profit['레버리지']}\n"
        f"- 청산가: {profit['청산가']}\n"
        f"- 청산까지 남은 거리: {profit['청산까지 남은 거리']}\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"💸 손익 정보\n"
        f"- 미실현 손익: {profit['미실현 손익']}\n"
        f"- 실현 손익: {profit['실현 손익']}\n"
        f"- 진입 자산: {profit['진입 자산']}\n"
        f"- 수익률: {profit['수익률']}\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"🧠 멘탈 케어\n"
        f"오늘 수익이 적다고 아쉬워 마세요. 한 번의 승리가 내일의 기회를 만듭니다! 😊\n"
        f"━━━━━━━━━━━━━━━━━━━"
    )
    await context.bot.send_message(chat_id=update.effective_chat.id, text=msg)

async def handle_forecast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await handle_report(update, context)

async def handle_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = f"📅 작성 시각: {kr_now_str()}\n📡 예정 주요 이벤트\n- 예시: 2025-05-21 18:00 비트코인 현물 ETF 심사 마감"
    await context.bot.send_message(chat_id=update.effective_chat.id, text=msg)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await handle_report(update, context)

def run_telegram_bot():
    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("report", handle_report))
    application.add_handler(CommandHandler("profit", handle_profit))
    application.add_handler(CommandHandler("forecast", handle_forecast))
    application.add_handler(CommandHandler("schedule", handle_schedule))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    application.run_polling()
