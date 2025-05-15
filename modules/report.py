import os
import openai
from modules.data_fetch import fetch_ohlcv, calc_technical_indicators, get_latest_price
from modules.constants import OPENAI_API_KEY

openai.api_key = OPENAI_API_KEY

def build_and_send_report():
    # 1) 데이터 수집
    df = fetch_ohlcv(limit=100)
    df = calc_technical_indicators(df)
    price = get_latest_price()

    # 2) 가장 최신 바(현재) 지표
    latest = df.iloc[-1]
    tech_summary = (
        f"현재가: ${price:.2f}\n"
        f"RSI(14): {latest.rsi:.1f}, MACD: {latest.MACD_12_26_9:.4f}, Signal: {latest.MACDs_12_26_9:.4f}\n"
        f"MA20/50/200: {latest.ma20:.2f}/{df['close'].rolling(50).mean().iloc[-1]:.2f}/{df['close'].rolling(200).mean().iloc[-1]:.2f}\n"
        f"Bollinger Upper/Lower: {latest.bb_upper:.2f}/{latest.bb_lower:.2f}"
    )

    # 3) GPT 프롬프트 작성 (실제 분석은 GPT에 위임)
    prompt = (
        "아래 실시간 시장 기술 지표를 바탕으로 12시간 BTC 예측 리포트를 작성해주세요.\n\n"
        f"{tech_summary}\n\n"
        "– 상승·하락 확률, 근거 요약, 전략 제안 포함\n"
    )

    resp = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "당신은 전문 암호화폐 애널리스트입니다."},
            {"role": "user",   "content": prompt}
        ],
        temperature=0.7,
    )
    return resp.choices[0].message.content
