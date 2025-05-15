import os
from datetime import datetime
from openai import OpenAI

client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

def get_prediction_report():
    prompt = (
        "매일 오전 9시, 오후 1시, 오후 11시에 GPT가 분석하는 비트코인 예측 리포트를 작성해주세요. "
        "분석 기준은 다음과 같습니다: "
        "1. 시장 이벤트 요약(CPI, FOMC, ETF 등)과 BTC에 미치는 영향(호재/악재/중립), "
        "2. RSI, MACD, MA, 볼린저밴드 등 기술 분석, "
        "3. 온체인 고래 이체, 펀딩비, 공포탐욕지수 등 구조/심리 지표, "
        "4. 12시간 상승/하락 확률 예측과 전략 요약, "
        "5. 예외 상황 실시간 감지, "
        "6. 이전 예측과 실제 시장 비교 및 오차 원인 피드백 포함, "
        "7. 모든 수치는 실시간 정보 기반으로 작성, "
        "8. 사용자 계정은 Telegram에서 수신하며, 자연어로 대화 가능함."
    )

    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "당신은 전문 암호화폐 전략 분석가입니다."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.7
    )

    return response.choices[0].message.content

def format_profit_report_text():
    # 향후 Bitget API 연결 시 자동화 가능
    realized_pnl = 31.4
    unrealized_pnl = -5.2
    entry_capital = 500  # 진입 자산

    total_pnl = realized_pnl + unrealized_pnl
    roi = (total_pnl / entry_capital) * 100
    krw_equiv = round(total_pnl * 1350)

    return f"""\
🧾 실현 손익: ${realized_pnl:.2f}
📉 미실현 손익: ${unrealized_pnl:.2f}
💰 총 손익: ${total_pnl:.2f} (≈ {krw_equiv} KRW)
📈 수익률: {roi:.2f}%
🕒 기준 시각: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
