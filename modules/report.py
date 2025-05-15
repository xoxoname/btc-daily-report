import requests
from datetime import datetime
import pytz

kst = pytz.timezone("Asia/Seoul")

def get_profit_report():
    try:
        response = requests.get("https://btc-daily-report.onrender.com/report")
        response.raise_for_status()
        return response.json()
    except Exception as e:
        return {"error": str(e)}

def format_profit_report_text(data):
    try:
        krw_pnl = data.get("krw_pnl", "N/A")
        usdt_pnl = data.get("usdt_pnl", "N/A")
        now_str = datetime.now(kst).strftime('%Y-%m-%d %H:%M:%S')
        return f"[{now_str} 기준]\n💰 실현 + 미실현 총 손익:\n- {usdt_pnl} USDT\n- 약 {krw_pnl} KRW"
    except Exception:
        return "손익 정보 분석 실패"

def get_prediction_report():
    try:
        # 실제 예측 API 호출 로직을 여기에 추가하세요.
        return {
            "market": "미국 CPI 발표: 예상치 부합 (2.4%) → 시장 안도감\nFOMC 발언 없음\n긴급 속보 없음",
            "technical": "MACD 하락 전환, RSI 68, MA(20/50) 이격 축소 → 기술적 조정 가능성",
            "psychology": "공포탐욕지수 72 (탐욕), 커뮤니티 정서는 낙관\nDXY 상승세 유지, BTC Dominance 상승",
            "forecast": {
                "up_probability": 42,
                "down_probability": 58,
                "summary": "📉 하락 가능성 우세: DXY 상승 + MACD 약세"
            },
            "exceptions": [],
            "feedback": {
                "match": "이전 예측과 유사함",
                "reason": "DXY 영향 지속 반영됨",
                "next": "심리 지표 반영 비중 보완 예정"
            }
        }
    except Exception as e:
        return {"error": str(e)}

def format_prediction_report_text(data):
    try:
        now_str = datetime.now(kst).strftime('%Y-%m-%d %H:%M')
        forecast = data.get("forecast", {})
        up = forecast.get("up_probability", "N/A")
        down = forecast.get("down_probability", "N/A")
        summary = forecast.get("summary", "")
        exceptions = ", ".join(data.get('exceptions', [])) or '특이사항 없음'
        fb = data.get('feedback', {})
        return f"""📌 BTC 매동 예측 보고서 ({now_str} KST)

[1. 시장 요인 요약]
{data.get('market', '정보 없음')}

[2. 기술적 분석]
{data.get('technical', '정보 없음')}

[3. 심리 및 구조 분석]
{data.get('psychology', '정보 없음')}

[4. 12시간 예측]
- 상승 확률: {up}%
- 하락 확률: {down}%
- 요약: {summary}

[5. 예외 감지]
{exceptions}

[6. 이전 예측 피드백]
- 평가: {fb.get('match', '정보 없음')}
- 사유: {fb.get('reason', '정보 없음')}
- 다음 보완 방향: {fb.get('next', '정보 없음')}

🧾 멘탈 코멘트: "한 순간의 수익에 흔들리지 마세요. 오늘도 꾸준한 전략이 답입니다."
"""
    except Exception:
        return "예측 리포트 분석 실패"
