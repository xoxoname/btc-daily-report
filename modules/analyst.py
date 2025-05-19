import openai
from datetime import datetime

def gpt_analyze(prompt: str, system_prompt=None):
    openai.api_key = "YOUR_OPENAI_API_KEY"  # 환경변수 사용 권장
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    try:
        response = openai.ChatCompletion.create(
            model="gpt-4o", messages=messages, temperature=0.3, timeout=20
        )
        return response['choices'][0]['message']['content'].strip()
    except Exception as e:
        return None, str(e)

def gpt_event_scan():
    prompt = "오늘과 앞으로 1일 이내 비트코인, 미국 CPI, FOMC, ETF 등 시장에 직접 영향 주는 주요 일정과 이벤트를 요약해줘. 일정별로 호재/중립/악재 간단 코멘트도."
    res, _ = gpt_analyze(prompt)
    return res or "일정 감지 실패"

def gpt_technical_analysis():
    prompt = "현재 비트코인 가격, 주요 지지선/저항선, RSI, 볼린저밴드, CVD, 심리 지표 등 종합 기술분석 결과를 핵심 위주로 요약해줘. 각 항목별로 호재/중립/악재 코멘트 포함."
    res, _ = gpt_analyze(prompt)
    return res or "기술적 분석 실패"

def gpt_sentiment_analysis():
    prompt = "비트코인 파생시장 심리, 펀딩비, 미결제약정, 공포탐욕지수, ETF 일정 등을 기반으로 구조적/심리적 분석 요약. 각 항목별로 호재/중립/악재 코멘트 포함."
    res, _ = gpt_analyze(prompt)
    return res or "심리 분석 실패"

def gpt_12h_forecast():
    prompt = "비트코인 12시간 내 상승/하락/횡보 확률과 단기 매매 전략을 분석해줘. 단, 현재 시장 상황을 반영해서 실제 투자자처럼 구체적이고 조심스럽게 코멘트."
    res, _ = gpt_analyze(prompt)
    return res or "예측 실패"

def gpt_exception_alert():
    prompt = "5분 전 대비 비트코인 가격 급등락, 트럼프 발언, ETF 승인, 대량 이체 등 긴급 시장변수 발생 여부와 위험요인만 엄선 요약. 악재/호재/경고도 붙여줘."
    res, _ = gpt_analyze(prompt)
    return res or "긴급 감지 실패"
