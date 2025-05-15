import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def get_prediction_report():
    try:
        completion = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "비트코인 시장 예측 전문가입니다."},
                {"role": "user", "content": "향후 12시간 비트코인 시세를 예측해줘."}
            ],
            max_tokens=1000,
            temperature=0.7,
        )
        return completion.choices[0].message.content.strip()
    except Exception as e:
        return f"예측 실패: {str(e)}"

def format_profit_report_text(profit_data):
    return f"""
📊 비트코인 수익 보고서

- 실현 손익: {profit_data['realized_pnl']} USDT
- 미실현 손익: {profit_data['unrealized_pnl']} USDT
- 총 자산: {profit_data['total_assets']} USDT
- 수익률: {profit_data['roi']} %

📅 기준 시각: {profit_data['timestamp']}
"""

def get_dummy_profit_data():
    return {
        "realized_pnl": "125.40",
        "unrealized_pnl": "-32.10",
        "total_assets": "1032.55",
        "roi": "12.4",
        "timestamp": "2025-05-15 14:00:00"
    }
