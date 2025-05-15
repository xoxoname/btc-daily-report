import os
from openai import OpenAI

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def get_prediction_report():
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "비트코인 리서치 전문가처럼 작성해 주세요."},
            {"role": "user", "content": "향후 12시간 예측 리포트 작성해줘. 기술적 분석, 시장 흐름, 심리 분석 포함해서."}
        ]
    )
    return response.choices[0].message.content

def format_profit_report_text():
    # 예시 수익 포맷
    return "현재 수익률: +3.2% (USD 320, 약 43만 원)"
