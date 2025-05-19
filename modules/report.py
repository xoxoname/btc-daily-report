import os
import datetime
import requests

async def generate_report():
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M (KST)")
    try:
        # Bitget API 예시 요청
        response = requests.get("https://api.bitget.com/api/mix/v1/market/ticker?symbol=BTCUSDT_UMCBL", timeout=5)
        data = response.json().get("data", {})
        price = data.get("last", "N/A")
    except Exception as e:
        return f"""📡 GPT 매동 예측 분석 리포트
📅 기준 시각: {now}
━━━━━━━━━━━━━━━━━━━
❌ 리포트 생성 실패: {e}
━━━━━━━━━━━━━━━━━━━"""

    return f"""📡 GPT 매동 예측 분석 리포트
📅 기준 시각: {now}
━━━━━━━━━━━━━━━━━━━
✅ 시스템은 정상 작동 중입니다.
현재 비트코인 가격: {price}
━━━━━━━━━━━━━━━━━━━"""