import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def get_prediction_report():
    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are a professional crypto analyst."},
                {"role": "user", "content": "Predict the next 12 hours of Bitcoin price movement."}
            ],
            temperature=0.7,
            max_tokens=1000
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"[오류] 예측 실패: {str(e)}"

def format_profit_report_text(profit_data):
    return f"""
📊 비트코인 수익 보고서

- 실현 손익: {profit_data['realized_pnl']} USDT
- 미실현 손익: {profit_data['unrealized_pnl']} USDT
- 총 자산: {profit_data['total_assets']} USDT
- 수익률: {profit_data['roi']} %

📅 기준 시각: {profit_data['timestamp']}
"""
