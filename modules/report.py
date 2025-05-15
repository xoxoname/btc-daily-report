from openai import OpenAI
import os

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def get_profit_report():
    return {
        "price": "64300.00",
        "usdt_pnl": 127.5,
        "krw_pnl": 172000,
    }

def get_prediction_report():
    completion = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "당신은 고급 암호화폐 트레이딩 분석가입니다."},
            {"role": "user", "content": "비트코인 향후 12시간 매동을 심리·기술·구조적 관점에서 예측해줘."}
        ],
        temperature=0.5
    )
    return completion.choices[0].message.content

def format_profit_report_text(data: dict) -> str:
    price = data.get("price", "N/A")
    usdt = data.get("usdt_pnl", 0)
    krw = data.get("krw_pnl", 0)
    return f"""💰 *수익 리포트*
- 현재 BTC 가격: `{price} USD`
- 실현 수익: `{usdt} USDT` (`{int(krw):,}원`)
"""

def format_prediction_report_text(text: str) -> str:
    return f"📈 *12시간 예측 리포트*\n{text}"
