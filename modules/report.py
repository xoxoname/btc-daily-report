import os
from openai import OpenAI
from datetime import datetime

# OpenAI 최신 버전(1.x)에 맞는 클라이언트 초기화 방식
client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY")
)

def get_prediction_report():
    prompt = "비트코인 향후 12시간 예측 리포트를 작성해줘. 현재 시장 상황을 기반으로 기술적 분석, 심리 분석, 구조적 요소를 포함해서."

    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "당신은 전문 암호화폐 분석가입니다."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.7
    )

    return response.choices[0].message.content

def format_profit_report_text():
    # Bitget 연동 전 임시 데이터
    realized_pnl = 31.4
    unrealized_pnl = -5.2

    return f"""\
🧾 실현 손익: ${realized_pnl:.2f}
📉 미실현 손익: ${unrealized_pnl:.2f}
🕒 기준 시각: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
