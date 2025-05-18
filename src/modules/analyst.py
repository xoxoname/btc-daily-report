import openai

class GPTForecaster:
    def __init__(self, api_key):
        openai.api_key = api_key

    def analyze(self, price, funding_rate, oi_change, volume, report_time):
        prompt = f"""📡 GPT 매동 예측 분석 리포트  
📅 기준 시각: {report_time}

━━━━━━━━━━━━━━━━━━━  
- 현재가: ${price:,.0f}
- 펀딩비: {funding_rate:.4f}
- 미결제약정 변화: {oi_change}
- 거래량: {volume} BTC

━━━━━━━━━━━━━━━━━━━  
아래 항목에 따라 분석 및 예측 결과를 한국어로 상세하게 작성해줘.

1. 기술적 분석 (지지/저항선, RSI 등)
2. 심리/구조 분석 (펀딩비, 미결제약정, 포지션 쏠림 등)
3. 12시간 가격 예측 (상승/횡보/하락 확률)
4. 전략 제안 (진입/청산/리스크 코멘트)
5. 멘탈 케어 한마디

출력은 Markdown 스타일로, 각 항목별 구분선을 넣어줘.
"""
        response = openai.ChatCompletion.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content
