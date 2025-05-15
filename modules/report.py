import os
import requests
import openai
from dotenv import load_dotenv

load_dotenv()

openai.api_key = os.getenv("OPENAI_API_KEY")

REPORT_URL = "https://btc-daily-report.onrender.com/report"


def get_profit_report():
    try:
        response = requests.get(REPORT_URL)
        if response.status_code != 200:
            return f"🚨 리포트 API 오류: 상태 코드 {response.status_code}"

        data = response.json()
        summary = data.get("summary", "요약 없음")
        realized = data.get("realized", {})
        unrealized = data.get("unrealized", {})

        result = f"""📊 실현 손익 리포트
- 한 줄 요약: {summary}

[실현 손익]
- 수익률: {realized.get("profit_rate", "N/A")}%
- 손익: ${realized.get("profit", "N/A")} (≈ {realized.get("profit_krw", "N/A")}원)

[미실현 손익]
- 수익률: {unrealized.get("profit_rate", "N/A")}%
- 손익: ${unrealized.get("profit", "N/A")} (≈ {unrealized.get("profit_krw", "N/A")}원)
"""
        return result

    except Exception as e:
        return f"🚨 손익 리포트 생성 실패: {e}"


def get_prediction_report():
    try:
        response = requests.get(REPORT_URL)
        if response.status_code != 200:
            return f"🚨 리포트 API 오류: 상태 코드 {response.status_code}"

        data = response.json()
        prediction_input = data.get("prediction_input", "")

        if not prediction_input:
            return "📭 예측 입력이 비어 있습니다."

        response = openai.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "너는 금융시장 분석가로, BTC 시장 분석 리포트를 생성하는 역할을 맡고 있어."},
                {"role": "user", "content": prediction_input}
            ],
            temperature=0.7
        )

        result_text = response.choices[0].message.content
        return f"📈 비트코인 예측 리포트\n\n{result_text}"

    except Exception as e:
        return f"🚨 예측 리포트 생성 실패: {e}"
