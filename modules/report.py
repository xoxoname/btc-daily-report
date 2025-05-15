import os
from openai import OpenAI
from modules.constants import SYSTEM_PROMPT
from modules.utils import fetch_report_data

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def get_profit_report():
    # 추후 Bitget API 연동 예정
    return "수익 리포트 기능은 현재 준비 중입니다."

def generate_prediction_report():
    report_data = fetch_report_data()

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": report_data}
    ]

    chat_completion = client.chat.completions.create(
        model="gpt-4",
        messages=messages,
        temperature=0.7,
        max_tokens=1500
    )

    return chat_completion.choices[0].message.content.strip()
