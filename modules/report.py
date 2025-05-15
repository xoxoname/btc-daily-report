# modules/report.py

import os
from datetime import datetime
from openai import OpenAI

# ✅ 최신 방식으로 수정
client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
)

def get_prediction_report():
    prompt = """
당신은 전문 비트코인 분석가입니다. 다음 기준에 따라 12시간 예측 리포트를 작성하세요.

1. 📊 [시장 이벤트 요약]
- 오늘 발표된 미국 경제지표 요약 (호재/악재 구분 포함)
- 연준 발언 및 트럼프/바이든 이슈 요약
- ETF 승인, 해킹 등 특이 속보 여부 포함
- 미국 증시 개장 전 주요 실적 발표 및 BTC 영향 요약

2. 📈 [기술적 분석]
- RSI, MACD, 이동평균(20/50/200), 볼린저밴드, 피보나치, 이치모쿠, 캔들패턴 등 종합
- 파생: 펀딩비, 오픈이자, 롱숏비율, CVD, 유동성맵

3. 🧠 [심리 및 구조]
- 공포탐욕지수, 트위터/X 여론, 자금 흐름(DXY, ETH/BTC)
- ETF 유입/유출, 옵션 만기/기관 리밸런싱

4. 📌 [12시간 예측]
- 상승/하락 확률(%), 근거 간결 요약, 전략 제시

5. ⚠️ [예외 감지]
- 예상 외 이벤트 시 알림 추천 여부 포함

6. 🧾 [예측 검증]
- 12시간 전 예측과 비교, 오차 원인 및 개선 요약

분석은 구조적으로, 각 지표와 차트 근거를 통합하여 작성할 것.
    """

    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "당신은 세계 최고의 크립토 전략가입니다."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.7
    )
    return response.choices[0].message.content

def format_profit_report_text():
    realized_pnl = 31.4
    unrealized_pnl = -5.2
    entry_asset = 520.0
    total_pnl = realized_pnl + unrealized_pnl
    profit_rate = (total_pnl / entry_asset) * 100

    return f"""\
🧾 실현 손익: ${realized_pnl:.2f}
📉 미실현 손익: ${unrealized_pnl:.2f}
💰 총 손익: ${total_pnl:.2f}
📈 수익률: {profit_rate:.2f}%
🕒 기준 시각: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
