import os
from openai import OpenAI
from datetime import datetime

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def get_prediction_report():
    prompt = """비트코인 향후 12시간 예측 리포트를 작성해줘.
- 현재 시장 상황 기반으로 정밀 분석
- 📊 시장 이벤트 요약: 주요 발표, 정치 발언, ETF 속보 등 (BTC에 호재/악재 여부 포함)
- 📈 기술적 분석: RSI, MACD, 이평선, 파생시장, 유동성
- 🧠 심리/구조 지표: 공포탐욕지수, 온체인, ETF 자금 흐름, DXY 등
- 📌 12시간 예측: 상승/하락 확률 %, 전략 요약
- ⚠️ 예외 감지: 속보 있으면 바로 알림
- 🔍 이전 예측 검증 및 오차 설명
- 전략 인사이트는 사람 분석자처럼 논리적이고 구조적으로 정리해줘"""

    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "당신은 전문 암호화폐 시장 분석가입니다. 모든 정보를 구조화하고 투자자에게 정밀한 전략을 제공합니다."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.7
    )

    return response.choices[0].message.content

def format_profit_report_text():
    realized_pnl = 128.4
    unrealized_pnl = -20.3
    entry_asset = 500.0

    total_pnl = realized_pnl + unrealized_pnl
    return f"""\
🧾 실현 손익: ${realized_pnl:.2f} ≈ {realized_pnl * 1350:.1f}원
📉 미실현 손익: ${unrealized_pnl:.2f} ≈ {unrealized_pnl * 1350:.1f}원
📊 총 손익: ${total_pnl:.2f} ≈ {total_pnl * 1350:.1f}원
📈 수익률: {total_pnl / entry_asset * 100:.2f}% (진입 자산 ${entry_asset:.2f} 기준)
🕒 기준 시각: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
