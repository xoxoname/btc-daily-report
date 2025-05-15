import os
from openai import OpenAI
from modules.constants import SYSTEM_PROMPT
from modules.utils import fetch_report_data

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def get_profit_report():
    return fetch_report_data()["profit"]

def get_prediction_report():
    profit = fetch_report_data()["profit"]
    prediction_prompt = f"{SYSTEM_PROMPT}\n\n현재 BTC 상황:\n{profit}"
    completion = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prediction_prompt},
        ],
        temperature=0.5,
        max_tokens=1000,
    )
    return completion.choices[0].message.content.strip()

def format_profit_report_text(profit: dict) -> str:
    return (
        f"💰 *현재가*: {profit.get('price')} USD\n"
        f"📈 *실현손익*: {profit.get('usdt_pnl')} USDT ({profit.get('krw_pnl')} KRW 기준)"
    )

def format_prediction_report_text(prediction: str) -> str:
    return f"📊 *예측 분석 결과*\n{prediction}"
