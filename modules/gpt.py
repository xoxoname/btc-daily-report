import os
import random
from openai import OpenAI

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
client = OpenAI(api_key=OPENAI_API_KEY)

def ask_gpt(prompt, max_tokens=220, temperature=0.85):
    completion = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "system", "content": prompt}],
        max_tokens=max_tokens,
        temperature=temperature,
    )
    return completion.choices[0].message.content.strip()

def get_dynamic_mental_comment(pnl, day_pnl_krw, last7=None, last14=None):
    base = []
    if pnl > 0:
        base = [
            f"오늘 선물로 {day_pnl_krw:,}원을 벌었어요. 이 수익은 편의점 알바 {day_pnl_krw // 8000}시간을 해야 벌 수 있는 돈이에요! 지금은 수익을 지키며 차분히 다음 타점을 기다려 보세요.",
            f"수익도 좋지만, 꾸준히 지키는 습관이 더 중요해요. 오늘 수익은 잠깐의 기쁨, 내일은 새로운 시작!",
            f"축하해요! 오늘의 수익은 한달 넷플릭스 구독료 {day_pnl_krw // 17000}개월치를 벌었습니다. 내일은 다시 차분하게 시장을 보며 기회를 기다려봐요.",
        ]
    elif pnl < 0:
        base = [
            f"손실이 있어도 괜찮아요. 시장은 항상 새로운 기회를 주니까, 충동적으로 추가 진입하지 말고 오늘은 휴식도 좋겠어요.",
            f"오늘 손실이 {abs(day_pnl_krw):,}원 발생했지만, 최근 7일간 평균 수익이 {last7 or 0}%라면 충분히 복구할 수 있습니다. 침착하게 전략을 지켜봐요.",
            "크게 흔들릴 필요 없습니다. 장기적인 승자가 되려면 단기 손실에도 흔들리지 않는 멘탈이 중요해요.",
        ]
    else:
        base = [
            "오늘은 수익도 손실도 없는 조용한 날이에요. 다음 기회를 차분히 준비해봐요.",
            "변동성이 적은 날엔 마음도 쉬어가세요.",
        ]
    return random.choice(base)
