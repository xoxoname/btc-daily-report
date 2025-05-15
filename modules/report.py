import os
from openai import OpenAI

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def get_prediction_report():
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a professional crypto market analyst."},
            {"role": "user", "content": "비트코인 향후 12시간 매매 예측 리포트를 작성해줘. 시장 동향, 기술 지표, 심리 분석 포함해서."}
        ],
        temperature=0.7
    )
    return response.choices[0].message.content

def format_profit_report_text(data):
    return (
        f"📊 실현 손익: {data['realized_pnl']} USDT\n"
        f"📈 미실현 손익: {data['unrealized_pnl']} USDT\n"
        f"💰 총자산: {data['total_assets']} USDT\n"
        f"📌 수익률: {data['roi']}%\n"
        f"⏰ 기준 시각: {data['timestamp']}"
    )
