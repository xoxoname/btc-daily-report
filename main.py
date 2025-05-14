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

def fetch_open_positions(product_type="USDT-FUTURES", margin_coin="USDT"):
    path = "/api/mix/v1/position/all-position"  # ✅ Bitget 공식 API 경로
    query = f"productType={product_type}&marginCoin={margin_coin}"
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
        return res.json().get("data", [])
    except Exception as e:
        print("❌ Bitget API 호출 실패:", str(e))
        return []

def main():
    now = datetime.now(timezone("Asia/Seoul")).strftime("%Y-%m-%d %H:%M:%S")
    positions = fetch_open_positions()

    print("📈 [BTC 실시간 포지션 수익 요약 - 현재 보유 중인 종목 기준]")
    print(f"시각: {now}")

    if not positions:
        print("📭 현재 보유 중인 포지션이 없습니다.")
        return

    rate = 1335
    found = False

    for pos in positions:
        symbol = pos.get("symbol")
        side = pos.get("holdSide", "unknown")
        entry = float(pos.get("entryPrice", 0))
        current = float(pos.get("marketPrice", 0))
        unrealized = float(pos.get("unrealizedPL", 0))

        if unrealized == 0:
            continue

        found = True
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
        print("✅ 포지션은 있으나 수익은 아직 발생하지 않았습니다.")

if __name__ == "__main__":
    main()
