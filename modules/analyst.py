import openai
from datetime import datetime

openai.api_key = "YOUR_OPENAI_API_KEY"

def gpt_analyze(prompt: str) -> str:
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "너는 금융 전문가야. 아래 내용을 바탕으로 분석해줘."},
                {"role": "user", "content": prompt}
            ]
        )
        return response['choices'][0]['message']['content'].strip()
    except Exception as e:
        return f"⚠️ GPT 분석 실패: {e}"
