import os
import requests
from datetime import datetime
from pytz import timezone
from dotenv import load_dotenv

# 환경 변수 불러오기 (.env)
load_dotenv()

API_KEY = os.getenv("BITGET_API_KEY")
SECRET_KEY = os.getenv("BITGET_SECRET_KEY")

def fetch_sample_pnl():
    """
    실제 API 연동 전 테스트용 수익 분석 함수입니다.
    추후 Bitget API 연동 시 accountBill 또는 positionHistory 등으로 교체 가능합니다.
    """
    now = datetime.now(timezone("Asia/Seoul"))
    today = now.strftime("%Y-%m-%d")

    # 예시 수익
    profit_usd = 42.5
    exchange_rate = 1330  # 고정 환율 가정
    profit_krw = int(profit_usd * exchange_rate)

    return {
        "datetime": now.strftime("%Y-%m-%d %H:%M:%S"),
        "usd": profit_usd,
        "krw": profit_krw,
        "comment": "🔥 작은 이익도 매일 쌓이면 큰 흐름이 됩니다."
    }

if __name__ == "__main__":
    report = fetch_sample_pnl()
    print("📈 [BTC 수익 요약]")
    print(f"시각: {report['datetime']}")
    print(f"수익: +${report['usd']}")
    print(f"한화 약 {report['krw']}원 (편의점 알바 2.5시간)")
    print(report['comment'])
