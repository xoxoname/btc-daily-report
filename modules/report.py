import os
from openai import OpenAI
from modules.constants import SYSTEM_PROMPT
from modules.utils import fetch_report_data

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def get_profit_report():
    # 향후 Bitget API 기반 수익 리포트 구현 예정
    return "수익 리포트는 현재 미구현 상태입니다."


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
