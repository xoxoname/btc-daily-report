# modules/utils.py

import os
import requests
from datetime import datetime
from pytz import timezone

def get_current_timestamp():
    now = datetime.now(timezone("Asia/Seoul"))
    return now.strftime("%Y-%m-%d %H:%M")

def format_usd(value):
    return f"${value:,.2f}"

def format_krw(value):
    return f"{int(value):,}원"

# 🔌 비트겟 실시간 포지션 및 수익 정보 (현재는 mock)
def get_bitget_data():
    # 실제 Bitget API 연동 시 여기에 구현
    return {
        "positions": [
            {
                "symbol": "BTCUSDT",
                "entry_price": 10200.00,
                "current_price": 10050.00,
                "pnl_usd": -150.00,
                "pnl_krw": -205000
            }
        ],
        "return_rate": -7.1,
        "realized": -20.00,
        "deposit": 2100.00,
        "now_asset": 1930.00,
        "total_pnl": 170.00,
        "total_krw": 232000,
        "weekly_return": 4.2
    }

# 📄 GPT 예측 결과 저장 및 불러오기
def save_prediction(text):
    with open("latest_prediction.txt", "w", encoding="utf-8") as f:
        f.write(text)

def load_previous_prediction():
    try:
        with open("latest_prediction.txt", "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return "(이전 예측 없음)"

# 📅 향후 7일간 일정 제공
def get_schedule_data():
    return [
        {"date": "5월 17일", "event": "트럼프 대통령 연설", "impact": "시장에 긍정적 신호 제공 가능성"},
        {"date": "5월 20일", "event": "연준 금리 발표", "impact": "시장 변동성 증가 예상"},
        {"date": "5월 22일", "event": "미-중 무역 회담", "impact": "시장 안정성 영향 가능성"},
        {"date": "5월 25일", "event": "비트코인 국제 컨퍼런스", "impact": "시장 관심도 증가 예상"}
    ]
