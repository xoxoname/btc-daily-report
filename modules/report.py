import os
from openai import OpenAI
import logging

openai.api_key = os.getenv("OPENAI_API_KEY")

def get_profit_report():
    # 실현 및 미실현 수익 데이터 (예시용)
    return {
        "price": "64,200 USDT",
        "usdt_pnl": 125.3,
        "krw_pnl": 173000,
    }

def format_profit_report_text(profit: dict) -> str:
    usdt_pnl = profit.get("usdt_pnl", 0)
    krw_pnl = profit.get("krw_pnl", 0)
    comment = "📈 수익 중입니다!" if usdt_pnl > 0 else "📉 손실 발생 중입니다."
    return f"""💰 *현재 수익 요약*\n\
현재가: {profit.get('price', 'N/A')}\n\
실현/미실현 손익: {usdt_pnl:.2f} USDT ({krw_pnl:,} KRW)\n\
{comment}"""

def get_prediction_report() -> str:
    try:
        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "비트코인 시장 분석가로서 다음 12시간 예측을 정밀하게 제공하세요."},
                {"role": "user", "content": "현재 비트코인 매매 동향을 기술적·심리적·구조적으로 분석하고, 다음 12시간 가격 방향을 예측해줘. 실현손익은 +125.3 USDT, 현재 가격은 64,200달러야."},
            ],
            temperature=0.3,
            max_tokens=800,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logging.exception("OpenAI 예측 실패")
        return "❗ 예측 생성 중 오류가 발생했습니다."
    
def format_prediction_report_text(prediction: str) -> str:
    return f"""📊 *12시간 예측 리포트*\n{prediction}"""
