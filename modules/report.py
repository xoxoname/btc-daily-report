import os
import openai
from modules.constants import SYSTEM_PROMPT
from modules.utils import fetch_report_data

openai.api_key = os.getenv("OPENAI_API_KEY")


def generate_prediction_report():
    report_data = fetch_report_data()

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": report_data}
    ]

    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=messages,
        temperature=0.7,
        max_tokens=1500,
    )

    return response.choices[0].message.content.strip()
