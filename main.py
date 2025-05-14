import os
import requests
from datetime import datetime
from pytz import timezone
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("BITGET_API_KEY")
SECRET_KEY = os.getenv("BITGET_SECRET_KEY")

def fetch_sample_report():
    now = datetime.now(timezone("Asia/Seoul")).strftime("%Y-%m-%d %H:%M:%S")
    return f"📈 [BTC 수익 요약]\n시각: {now}\n수익: +$42.5\n한화 약 57,000원 (편의점 알바 2.5시간)\n🔥 작은 이익도 매일 쌓이면 큰 흐름이 됩니다."

if __name__ == "__main__":
    report = fetch_sample_report()
    print(report)
