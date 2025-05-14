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

def fetch_unrealized_pnl(symbol="BTCUSDT", margin_coin="USDT"):
    path = "/api/mix/v1/position/single-position"
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
        res = requests.get(url, headers=headers)
        res.raise_for_status()
        data = res.json()

        pos = data.get("data", {})
        if not pos or float(pos.get("total", 0)) == 0:
            return None, None, None, None

        return (
            float(pos.get("unrealizedPL", 0)),
            float(pos.get("entryPrice", 0)),
            float(pos.get("marketPrice", 0)),
            pos.get("holdSide", "unknown")
        )

    except Exception as e:
        print("❌ Bitget API 호출 실패:", str(e))
        return None, None, None, None

def main():
    now = datetime.now(timezone("Asia/Seoul")).strftime("%Y-%m-%d %H:%M:%S")
    profit, entry, current, side = fetch_unrealized_pnl()

    print("📈 [BTC 실시간 미실현 수익 요약]")
    print(f"시각: {now}")

    if profit is None:
        print("현재 보유 중인 포지션이 없습니다.")
        return

    rate = 1335
    profit_krw = int(profit * rate)
    print(f"포지션 방향: {side.upper()} | 진입가: {entry} | 현재가: {current}")
    print(f"미실현 수익: {'+' if profit >= 0 else ''}${profit:.2f}")
    print(f"한화 약 {profit_krw:,}원")

    if profit > 0:
        print("✅ 현재 수익 중입니다! 청산 타이밍을 고민해보세요.")
    elif profit < 0:
        print("⚠️ 손실 상태입니다. 전략을 다시 점검해보세요.")
    else:
        print("😐 수익도 손실도 없는 상태입니다.")

if __name__ == "__main__":
    main()
