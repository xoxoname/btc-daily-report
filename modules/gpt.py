import os
import openai
import random

openai.api_key = os.getenv("OPENAI_API_KEY")

def get_gpt_comment(pnl_percent, profit):
    # 코멘트 prompt, 최대 100자, 상황별로 충동 억제 문구 유도
    prompt = f"""
아래는 비트코인 선물 실현/미실현 수익 상황에 따른 멘탈 케어 코멘트 예시입니다.

조건:
- 오늘 손익은 {profit:.2f} USDT, 수익률은 {pnl_percent:.2f}%.
- 사용자가 수익에 도취해 충동 매매하지 않게 유도할 것.
- 지나친 위로/격려만 말고, 오늘 성과를 현실에 비유하고 내일 무리한 진입을 자제하도록 안내.
- 매번 코멘트가 중복되지 않도록 1~2문장으로 센스있고 길이·톤을 다양하게 작성.

예시)
- 오늘 수익으로 배달음식 3번 시켜먹을 수 있습니다. 이젠 여유롭게 내일 타점을 기다려보세요!
- 큰 이익을 얻었으니 오늘은 '노터치' 데이로 마음의 휴식도 가져보는 건 어떨까요?
- 작은 손실은 투자 과정의 일부입니다. 심호흡 한 번 하고 충동 매매를 피하세요!
- 알바 10시간을 대신한 오늘의 수익, 내일은 무리하지 않고 지켜보는 여유도 필요합니다.

지금 상황에 맞는 오늘의 멘탈 케어 코멘트 1개만 답변하세요.
    """
    response = openai.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "system", "content": prompt}],
        max_tokens=100,
        temperature=random.uniform(0.7, 0.9)
    )
    text = response.choices[0].message.content.strip()
    return text
