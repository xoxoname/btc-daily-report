# modules/report.py
import requests
from datetime import datetime
import pytz

kst = pytz.timezone("Asia/Seoul")

def get_profit_report():
    try:
        resp = requests.get("https://<YOUR_DOMAIN>/report")
        return resp.json()
    except Exception as e:
        return {"error": str(e)}

def format_profit_report_text(data):
    now = datetime.now(kst).strftime('%Y-%m-%d %H:%M:%S')
    krw_pnl = data.get("krw_pnl", "N/A")
    usdt_pnl = data.get("usdt_pnl", "N/A")
    return f"[{now} 기준]\n💰 실현+미실현 총 손익:\n- {usdt_pnl} USDT\n- 약 {krw_pnl} KRW"

def get_prediction_report():
    # 더 이상 내부 하드코딩되지 않도록, 실제 API 연동으로 변경하세요.
    return {
        "market":     "미국 CPI 발표: 예상치 부합 (2.4%) → 시장 안도감",
        "technical":  "MACD 하락 전환, RSI 68 → 조정 가능성",
        "psychology": "공포탐욕지수 72 (탐욕)",
        "forecast": {
            "up_probability":   42,
            "down_probability": 58,
            "summary":          "하락 가능성 우세"
        },
        "exceptions": [],
        "feedback": {
            "match": "이전 예측과 유사",
            "reason": "DXY 영향 지속",
            "next":   "심리 지표 보완 예정"
        }
    }

def format_prediction_report_text(data):
    now = datetime.now(kst).strftime('%Y-%m-%d %H:%M')
    f = data.get("forecast", {})
    return (
        f"📌 BTC 예측 보고서 ({now} KST)\n\n"
        f"[1] 시장 요인:\n{data.get('market')}\n\n"
        f"[2] 기술 분석:\n{data.get('technical')}\n\n"
        f"[3] 심리 분석:\n{data.get('psychology')}\n\n"
        f"[4] 12시간 예측:\n"
        f"- 상승: {f.get('up_probability')}%\n"
        f"- 하락: {f.get('down_probability')}%\n"
        f"- 요약: {f.get('summary')}\n\n"
        f"[5] 예외 감지: {', '.join(data.get('exceptions')) or '없음'}\n\n"
        f"[6] 피드백:\n"
        f"- 평가: {data['feedback']['match']}\n"
        f"- 이유: {data['feedback']['reason']}\n"
        f"- 다음: {data['feedback']['next']}\n\n"
        f"🧾 멘탈 코멘트: 꾸준함이 답입니다."
    )
