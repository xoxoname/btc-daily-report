import os
import requests
from datetime import datetime
from flask import request
from telegram import Bot

# 🔐 텔레그램 인증
def authorized():
    chat_id = request.json.get("message", {}).get("chat", {}).get("id", "")
    return str(chat_id) == os.getenv("TELEGRAM_CHAT_ID")

# 🕒 현재 시각 포맷팅
def get_current_timestamp():
    now = datetime.now()
    return now.strftime("%Y년 %m월 %d일 %p %I:%M").replace("AM", "오전").replace("PM", "오후")

# 💲 USD 및 원화 포맷팅
def format_usd(value):
    return f"${value:,.2f}"

def format_krw(value):
    return f"{int(value):,}원"

# 🧾 비트겟 실시간 데이터 수집
def get_bitget_data():
    import random
    # ⚠️ 실제 Bitget API 연동 시 아래 코드 제거하고 실제 API 사용
    return {
        "positions": [{
            "symbol": "BTCUSDT",
            "entry_price": 10200,
            "current_price": 10310,
            "pnl_usd": 78.5,
            "pnl_krw": 107000
        }],
        "realized": 55.4,
        "deposit": 2100,
        "now_asset": 2233.9,
        "total_pnl": 133.9,
        "total_krw": 183000,
        "return_rate": 6.37,
        "weekly_return": 4.2
    }

# 📤 텔레그램 메시지 전송
def send_telegram_message(msg):
    bot = Bot(token=os.getenv("TELEGRAM_BOT_TOKEN"))
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    bot.send_message(chat_id=chat_id, text=msg, parse_mode="Markdown")

# 🧠 GPT 예측 저장 (더미: 실제 저장은 미구현)
def save_prediction(data: dict):
    print("예측 저장 완료 (임시)")

# 🧠 이전 GPT 예측 불러오기 (더미)
def load_previous_prediction():
    return {
        "전일 예측": "상승",
        "전일 실제": "상승",
        "피드백": "예측 적중 (변동 구간도 정확)"
    }

# 🧠 예측 적중 여부 판단 (더미)
def get_prediction_result():
    return "✅ 예측 적중 (전일 예측: 상승 / 실제: 상승)"
