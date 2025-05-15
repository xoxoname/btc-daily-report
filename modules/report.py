import os
from openai import OpenAI
from datetime import datetime

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def get_prediction_report():
    prompt = (
        "📌 비트코인 향후 12시간 예측 리포트를 작성해줘.\n"
        "1. 시장 이벤트 및 매크로 요약 (이슈별로 호재/악재 여부 표시)\n"
        "2. 기술적 분석: RSI, MACD, MA20/50/200, 파생지표 포함\n"
        "3. 심리/구조 지표 요약\n"
        "4. 상승/하락 확률 수치, 전략 요약\n"
        "5. 예외 발생 시 대처 전략 포함\n"
        "6. 12시간 전 예측과 실제 비교 및 피드백\n"
        "→ 형식 구조화 + 전략적 인사이트 강조 + 수치는 반드시 표기"
    )

    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "당신은 전문 암호화폐 애널리스트입니다."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.4,
    )
    return response.choices[0].message.content.strip()

def format_profit_report_text():
    # 임시 샘플 (추후 Bitget 연동 예정)
    realized_pnl = 31.4
    unrealized_pnl = -5.2
    entry_capital = 1000.0

    total_pnl = realized_pnl + unrealized_pnl
    pnl_ratio = (total_pnl / entry_capital) * 100

    krw_rate = 1380
    total_krw = total_pnl * krw_rate

    return f"""\
💰 실현 손익: ${realized_pnl:.2f}
📉 미실현 손익: ${unrealized_pnl:.2f}
📊 수익률: {pnl_ratio:.2f}%
💵 한화 환산: 약 {total_krw:,.0f}원
🕒 기준 시각: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
