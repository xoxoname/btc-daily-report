import openai
import random
from modules.constants import OPENAI_API_KEY

openai.api_key = OPENAI_API_KEY

def gpt_analyze(system_prompt, user_prompt):
    response = openai.ChatCompletion.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        max_tokens=1200,
        temperature=0.85,
    )
    return response['choices'][0]['message']['content'].strip()

def random_mental_comment(pnl):
    # Example - Customize with more creative outputs as needed
    if pnl > 10:
        return "오늘 수익으로 주말 호텔 1박 예약 가능합니다! 시장의 흐름에 감사하며, 쉬는 것도 전략입니다."
    elif pnl > 1:
        return "수익의 시작! 오늘 수익으로 치킨 2마리 파티도 가능하네요. 감정 컨트롤을 유지하며 한 템포 쉬는 것도 중요합니다."
    elif pnl > -1:
        return "거의 본전입니다. 무리한 매매는 금물! 내일 더 좋은 기회를 노려봐요."
    elif pnl > -5:
        return "작은 손실은 성장의 씨앗! 다시 천천히 진입 타이밍을 노려봅시다."
    else:
        return "큰 손실이지만, 반등의 기회도 곧 옵니다. 시스템을 믿고 초심을 지켜요."
