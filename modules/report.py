from openai import OpenAI
from datetime import datetime
import os

# 최신 방식으로 클라이언트 생성
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def get_prediction_report():
    prompt = (
        "비트코인 향후 12시간 예측 리포트를 작성해줘. 다음 기준을 반드시 반영할 것:\n"
        "- 📊 시장 이벤트 요약: CPI 등 지표, 증시 실적, 긴급 속보 (예: ETF 승인 등), 정치 발언 등 각 항목별 BTC에 호재/악재 여부 포함\n"
        "- 📈 기술적 분석: RSI, MACD, MA, 볼린저밴드, 피보나치, Ichimoku, 캔들 패턴, 파생시장 지표 (펀딩비, 롱숏비, CVD 등)\n"
        "- 🧠 심리/구조 분석: 공포탐욕지수, 커뮤니티 여론, BTC Dominance, ETH/BTC, DXY, 미 국채, ETF 자금 흐름, 옵션 만기일 등\n"
        "- 📌 전략 요약: 향후 12시간 동안 상승/하락/보합 확률 (%)와 그 근거 포함\n"
        "- ⚠️ 예외 감지 및 긴급 변수 발생 시 실시간 반영\n"
        "- 🧾 지난 예측과 실제 결과 비교, 오차 원인 및 다음 개선점 요약 포함\n"
    )

    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "당신은 최고의 암호화폐 리서치 전문가입니다. 리포트는 실제 트레이딩 데스크 수준으로 심층 분석해 주세요."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.5
    )

    return response.choices[0].message.content

def format_profit_report_text():
    realized_pnl = 31.4
    unrealized_pnl = -5.2
    entry_capital = 1000  # 진입 자산

    total_pnl = realized_pnl + unrealized_pnl
    profit_rate = (total_pnl / entry_capital) * 100
    krw_rate = 1350  # 환율

    return f"""\
🧾 수익 리포트
--------------------
✅ 실현 손익: ${realized_pnl:.2f} (약 {realized_pnl * krw_rate:,.0f}원)
📉 미실현 손익: ${unrealized_pnl:.2f} (약 {unrealized_pnl * krw_rate:,.0f}원)
💰 총 수익: ${total_pnl:.2f} (약 {total_pnl * krw_rate:,.0f}원)
📊 수익률: {profit_rate:.2f}%
📆 기준 시각: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
