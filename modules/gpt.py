import openai
from .constants import OPENAI_API_KEY

openai.api_key = OPENAI_API_KEY

def analyze_market_gpt(context):
    prompt = (
        "다음은 비트코인 선물 시장의 실시간 계좌/포지션/가격/일정/뉴스 정보입니다. "
        "이 데이터를 기반으로 아래 형식에 따라 전문적이고 실시간 요약, 분석, 예측, 전략, 멘탈 관리 코멘트까지 작성해주세요.\n\n"
        f"{context}\n\n"
        "=====\n"
        "⚡️ 주요 시장 이벤트:\n"
        "📉 기술적 분석:\n"
        "🔎 심리/구조적 진단:\n"
        "⏳ 12시간 예측:\n"
        "🧭 전략 요약 및 멘탈 코멘트:\n"
        "====="
    )
    res = openai.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=850,
        temperature=0.8,
    )
    return res.choices[0].message.content.strip()
