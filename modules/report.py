import os
from openai import OpenAI
import requests
from httpx import Client as HttpxClient

# Render 환경에서 proxies 문제를 피하기 위해 직접 http_client 지정
http_client = HttpxClient(proxies=None)

client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    http_client=http_client
)

def get_prediction_report():
    try:
        completion = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "비트코인 매매 리포트를 생성해 주세요."},
                {"role": "user", "content": "오늘의 비트코인 시장 예측을 알려줘."}
            ],
            temperature=0.7,
        )
        return completion.choices[0].message.content
    except Exception as e:
        return f"[오류 발생] {str(e)}"

def format_profit_report_text(pnl_data):
    realized = pnl_data.get("realized_pnl", 0)
    unrealized = pnl_data.get("unrealized_pnl", 0)
    return f"📊 실현 손익: {realized} USDT\n📈 미실현 손익: {unrealized} USDT"
