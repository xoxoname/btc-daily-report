# main.py
import os
from dotenv import load_dotenv
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from datetime import datetime
import pytz

# 1. 환경변수 로드 & 검증
load_dotenv()
REQUIRED_VARS = [
    "BITGET_API_KEY",
    "BITGET_PASSPHRASE",
    "BITGET_SECRET",
    "OPENAI_API_KEY",
    "REPORT_URL",
    "TELEGRAM_TOKEN",
    "CHAT_ID",
]
for var in REQUIRED_VARS:
    if not os.getenv(var):
        raise RuntimeError(f"환경변수 {var} 가 설정되지 않았습니다!")

# 2. HTTP 세션 + 재시도 설정
session = requests.Session()
retry_strategy = Retry(
    total=3,
    backoff_factor=1,
    status_forcelist=[429, 500, 502, 503, 504],
)
adapter = HTTPAdapter(max_retries=retry_strategy)
session.mount("https://", adapter)
session.mount("http://", adapter)

# 3. 시간대 설정
kst = pytz.timezone("Asia/Seoul")

# 4. 리포트 가져오기
def get_profit_report():
    try:
        r = session.get(os.getenv("REPORT_URL"), timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        return {"error": str(e)}

# 5. 리포트 포맷팅
def format_profit_report_text(data):
    now = datetime.now(kst).strftime("%Y-%m-%d %H:%M:%S")
    if data.get("error"):
        return f"[{now}] 실현·미실현 손익 조회 실패: {data['error']}"
    krw = data.get("krw_pnl", "N/A")
    usdt = data.get("usdt_pnl", "N/A")
    return f"[{now} 기준]\n💰 총 손익:\n- {usdt} USDT\n- 약 {krw} KRW"

# 6. 예측 리포트 (예시)
def get_prediction_report():
    try:
        # 예시: 실제는 OpenAI나 다른 API 호출
        return {
            "market": "미국 CPI 발표: 예상치 부합 (2.4%) → 시장 안도",
            "technical": "MACD 하락 전환, RSI 68 → 기술적 조정 가능성",
            "psychology": "공포탐욕지수 72 (탐욕), BTC Dominance 상승",
            "forecast": {"up_probability": 42, "down_probability": 58, "summary": "하락 우세"},
            "exceptions": [],
            "feedback": {"match": "이전 예측과 유사", "reason": "DXY 영향 지속", "next": "심리 반영 보완"}
        }
    except Exception as e:
        return {"error": str(e)}

def format_prediction_report_text(data):
    now = datetime.now(kst).strftime("%Y-%m-%d %H:%M")
    if data.get("error"):
        return f"[{now}] 예측 리포트 조회 실패: {data['error']}"
    f = data["forecast"]
    return (
        f"📌 BTC 예측 보고서 ({now} KST)\n\n"
        f"[1] 시장 요인:\n{data['market']}\n\n"
        f"[2] 기술적 분석:\n{data['technical']}\n\n"
        f"[3] 심리·구조:\n{data['psychology']}\n\n"
        f"[4] 12시간 예측:\n"
        f"- 상승: {f['up_probability']}%\n"
        f"- 하락: {f['down_probability']}%\n"
        f"- 요약: {f['summary']}\n\n"
        f"[5] 예외사항: {', '.join(data['exceptions']) or '없음'}\n\n"
        f"[6] 이전 피드백:\n"
        f"- 평가: {data['feedback']['match']}\n"
        f"- 사유: {data['feedback']['reason']}\n"
        f"- 보완: {data['feedback']['next']}\n\n"
        f"🧾 멘탈 코멘트: 꾸준함이 답입니다."
    )

# 7. 텔레그램 전송
def send_telegram(text: str):
    token = os.getenv("TELEGRAM_TOKEN")
    chat_id = os.getenv("CHAT_ID")
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        resp = session.post(
            url,
            json={"chat_id": chat_id, "text": text},
            timeout=5
        )
        resp.raise_for_status()
    except Exception as e:
        print("텔레그램 전송 실패:", e)

# 8. 메인 실행 흐름
def main():
    profit = get_profit_report()
    send_telegram(format_profit_report_text(profit))

    prediction = get_prediction_report()
    send_telegram(format_prediction_report_text(prediction))

if __name__ == "__main__":
    main()
