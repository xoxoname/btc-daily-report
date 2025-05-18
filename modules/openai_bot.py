import os
import openai

openai.api_key = os.getenv("OPENAI_API_KEY")

def generate_forecast(prompt):
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "당신은 비트코인 시장 분석가입니다. 주어진 데이터를 바탕으로 12시간 매매 동향을 예측하고, 일정 형식에 맞춰 리포트를 작성하세요."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.4,
            max_tokens=1200
        )
        return response.choices[0].message["content"]
    except Exception as e:
        return f"❌ GPT 분석 실패: {str(e)}"