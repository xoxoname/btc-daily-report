import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
from modules.constants import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
from modules.report import build_report
from modules.utils import kr_now_str

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_chat.id, text="비트코인 예측 봇에 오신 것을 환영합니다!")

async def handle_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != TELEGRAM_CHAT_ID:
        return
    user_prompt = "실시간 BTC 시장 리포트 및 전략 분석을 아래 항목 순서대로 한국어로 작성: ..."
    market_data = ["ETF 승인 이슈 없음 → 호재", "FOMC 8시간 전 대기 중 → 악재 예상"]
    tech_data = ["현재가: $66,210", "RSI(4H): 61.5 (중립 강세) → 호재"]
    psych_data = ["펀딩비: +0.012% (롱 과열) → 호재", "공포탐욕지수: 71 (탐욕) → 호재"]
    forecast = ["상승 확률: 62%", "전략: 분할 매수/익절"]
    alerts = ["Whale Alert: 1,000 BTC 이체 감지 → 호재"]
    prev_check = ["5/17 23:00 횡보 예측 → 변동폭 ±0.9% → ✅ 적중"]
    pnl = {  # 반드시 dict!
        "진입 자산": "$2,000",
        "미실현 손익": "+$81.0 (11.0만원)",
        "실현 손익": "+$24.3 (3.3만원)",
        "금일 총 수익": "+$105.3 (14.3만원)",
        "수익률": "+5.26%"
    }
    msg = build_report(market_data, tech_data, psych_data, forecast, alerts, prev_check, pnl, user_prompt)
