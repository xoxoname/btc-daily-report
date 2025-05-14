import os
import requests
import time
import hmac
import hashlib
from datetime import datetime
from pytz import timezone
from dotenv import load_dotenv

# 환경변수 불러오기
load_dotenv()

API_KEY = os.getenv("BITGET_API_KEY")
SECRET_KEY = os.getenv("BITGET_SECRET_KEY")
PASSPHRASE = os.getenv("BITGET_PASSPHRASE")
BASE_URL = "https://api.bitget.com"

def get_timestamp():
    return str(int(time.time() * 1000))

def sign(message, secret_key):
    return hmac.new(secret_key.encode(), message.encode(), hashlib.sha256).hexdigest()

def fetch_single_position(symbol="BTCUSDT", margin_coin="USDT", product_type="USDT-FUTURES"):
    path = "/api/mix/v1/position/singlePosition"
    query = f"symbol={symbol}&marginCoin={margin_coin}"
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
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json().get("data", {})
        return data
    except Exception as e:
        print(f"❌ {symbol} API 호출 실패: {e}")
        return None

def main():
    now = datetime.now(timezone("Asia/Seoul")).strftime("%Y-%m-%d %H:%M:%S")
    print("📈 [실시간 포지션 수익 요약]")
    print(f"시각: {now}")

    symbols = ["BTCUSDT", "ETHUSDT", "XRPUSDT", "SOLUSDT", "DOGEUSDT"]
    rate = 1335
    found = False

    for symbol in symbols:
        pos = fetch_single_position(symbol=symbol)
        if not pos or float(pos.get("total", 0)) == 0:
            continue

        found = True
        side = pos.get("holdSide", "UNKNOWN")
        entry = float(pos.get("entryPrice", 0))
        current = float(pos.get("marketPrice", 0))
        unrealized = float(pos.get("unrealizedPL", 0))
        profit_krw = int(unrealized * rate)

        print(f"\n📌 종목: {symbol} | 방향: {side.upper()}")
        print(f"진입가: {entry} | 현재가: {current}")
        print(f"미실현 수익: {'+' if unrealized >= 0 else ''}${unrealized:.2f}")
        print(f"한화 약 {profit_krw:,}원")

        if unrealized > 0:
            print("✅ 현재 수익 중입니다!")
        elif unrealized < 0:
            print("⚠️ 손실 상태입니다. 전략 점검이 필요해요.")
        else:
            print("😐 수익도 손실도 없습니다.")

    if not found:
        print("📭 현재 포지션이 없거나 미실현 수익이 없습니다.")

if __name__ == "__main__":
    main()
