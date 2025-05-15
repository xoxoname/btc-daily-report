import os
from openai import OpenAI

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def get_prediction_report():
    completion = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "비트코인 시장 예측 전문가로 행동하세요."},
            {"role": "user", "content": "향후 12시간 BTC 매매 예측해줘."}
        ]
    )
    return completion.choices[0].message.content

def format_profit_report_text(realized_pnl, unrealized_pnl, total_assets):
    return f"""BTC 손익 요약

- 실현 손익: {realized_pnl} USDT
- 미실현 손익: {unrealized_pnl} USDT
- 총자산: {total_assets} USDT
"""
