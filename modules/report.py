# modules/report.py

import os
import openai
from datetime import datetime

# 1) API 키 설정 (환경변수 OPENAI_API_KEY)
openai.api_key = os.getenv("OPENAI_API_KEY")

def get_prediction_report():
    """비트코인 12시간 예측 리포트 생성"""
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "당신은 전문 암호화폐 분석가입니다."},
            {"role": "user", "content": (
                "📊 시장 이벤트 및 매크로 지표\n"
                "- 오늘 발표되는 미국 주요 경제지표, 연준/정치 뉴스, 증시 실적 일정, 긴급 속보\n"
                "📈 BTC 기술적 분석\n"
                "- RSI, MACD, 이동평균선(20/50/200), 볼린저, 피보나치, Ichimoku, 캔들\n"
                "- 파생시장 지표, 바이낸스 유동성 맵, 고래 온체인 트랙킹\n"
                "🧠 심리 지표 및 구조적 요소\n"
                "- 공포·탐욕 지수, 커뮤니티/트위터 심리, BTC Dominance, DXY, ETF 자금 흐름 등\n"
                "📌 12시간 예측 및 전략 요약\n"
                "- 상승/하락 확률(%), 간결 예측 근거, 전략 요약\n"
                "⚠️ 예외 상황 실시간 감지\n"
                "- 규제, 해킹, ETF 승인 등 특이 뉴스 즉시 알림\n"
                "🧾 이전 예측 검증 및 피드백 루프\n"
                "- 12시간 전 예측 vs 실제 비교, 오차 원인, 보완점 요약"
            )}
        ],
        temperature=0.7
    )
    return response.choices[0].message.content

def format_profit_report_text():
    """실현/미실현 손익 리포트 생성"""
    realized_pnl = 31.4    # 예시 값
    unrealized_pnl = -5.2  # 예시 값
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return (
        f"🧾 실현 손익: ${realized_pnl:.2f}\n"
        f"📉 미실현 손익: ${unrealized_pnl:.2f}\n"
        f"🕒 기준 시각: {now}"
    )
