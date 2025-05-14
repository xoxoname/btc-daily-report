import os
import requests
import time
import hmac
import hashlib
from datetime import datetime
from pytz import timezone
from dotenv import load_dotenv

# 환경 변수 로딩
load_dotenv()

API_KEY = os.getenv("BITGET_API_KEY")
SECRET_KEY = os.getenv("BITGET_SECRET_KEY")
PASSPHRASE = os.getenv("BITGET_PASSPHRASE")

BASE_URL = "https://api.bitget.com"

def get_timestamp():
    return str(int(time.time() * 1000))

def sign(message: str, secret_key: str):
    return hmac.new(secret_key.encode(), message.encode(), hashlib.sha256).hexdigest()

def fetch_today_pnl():
    now = datetime.now(timezone("Asia/Seoul"))
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end = now

    start_ts = int(start.timestamp() * 1000)
    end_ts = int(end.timestamp() * 1000)

    path = "/api/mix/v1/account/accountBill"
    query = f"productType=USDT-FUTURES&startTime={start_ts}&endTime={end_ts}&pageSize=50"
    timestamp = get_timestamp()
    message = f"{timestamp}GET{path}?{query}"
    signature = sign(message, SECRET_KEY)

    headers = {
        "ACCESS-KEY": API_KEY,
        "ACCESS-SIGN": signature,
        "ACCESS-TIMESTAMP": timestamp,
        "ACCESS-PASSPHRASE": PASSPHRASE,
        "Content-Type": "application/json"
    }

    url = f"{BASE_URL}{path}?{query}"

    try:
        res = requests.get(url, headers=headers)
        res.raise_for_status()
        data = res.json()

        total_pnl = 0.0
        for item in data.get("data", []):
            if item.get("billType") == "realized_pnl":
                total_pnl += float(item.get("amount", 0))

        return round(total_pnl, 2)

    except Exception as e:
        print("❌ Bitget API 호출 실패:", str(e))
        return None

def main():
    profit = fetch_today_pnl()
    now = datetime.now(timezone("Asia/Seoul")).strftime("%Y-%m-%d %H:%M:%S")

    if profit is None:
        print("❌ 오늘 수익 데이터를 가져오지 못했습니다.")
        return

    rate = 1335  # 환율
    profit_krw = int(profit * rate)

    print("📈 [BTC 실시간 수익 요약]")
    print(f"시각: {now}")
    print(f"수익: {'+' if profit >= 0 else ''}${profit:.2f}")
    print(f"한화 약 {profit_krw:,}원")

    if profit > 0:
        print("🎉 수익 축하드립니다! 오늘도 잘 해내셨어요.")
    elif profit < 0:
        print("🧘 손실은 과정일 뿐. 계속 꾸준히 전략을 따라가요.")
    else:
        print("📊 수익도 손실도 없었던 하루. 조용히 지나가는 것도 전략입니다.")

if __name__ == "__main__":
    main()

