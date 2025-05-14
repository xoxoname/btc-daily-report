import os
import requests
import time
import hmac
import hashlib
from datetime import datetime
from pytz import timezone
from dotenv import load_dotenv

# 환경 변수 로딩 (.env에 BITGET_API_KEY, BITGET_SECRET_KEY, BITGET_PASSPHRASE 설정)
load_dotenv()

API_KEY    = os.getenv("BITGET_API_KEY")
SECRET_KEY = os.getenv("BITGET_SECRET_KEY")
PASSPHRASE = os.getenv("BITGET_PASSPHRASE")
BASE_URL   = "https://api.bitget.com"

def get_timestamp():
    return str(int(time.time() * 1000))

def sign(message: str, secret_key: str):
    return hmac.new(secret_key.encode(), message.encode(), hashlib.sha256).hexdigest()

def fetch_all_positions(product_type="USDT-FUTURES", margin_coin="USDT"):
    path  = "/api/v2/mix/position/all-position"
    query = f"productType={product_type}&marginCoin={margin_coin}"
    ts    = get_timestamp()
    to_sign = f"{ts}GET{path}?{query}"
    signature = sign(to_sign, SECRET_KEY)

    headers = {
        "ACCESS-KEY":       API_KEY,
        "ACCESS-SIGN":      signature,
        "ACCESS-TIMESTAMP": ts,
        "ACCESS-PASSPHRASE": PASSPHRASE,
        "Content-Type":     "application/json"
    }
    url = f"{BASE_URL}{path}?{query}"

    try:
        res = requests.get(url, headers=headers)
        res.raise_for_status()
        return res.json().get("data", [])
    except Exception as e:
        print("❌ Bitget API 호출 실패:", e)
        return []

def main():
    now = datetime.now(timezone("Asia/Seoul")).strftime("%Y-%m-%d %H:%M:%S")
    positions = fetch_all_positions()

    print("📈 [실시간 포지션 수익 요약]")
    print(f"시각: {now}\n")

    if not positions:
        print("📭 현재 보유 중인 포지션이 없습니다.")
        return

    rate = 1335  # 환율
    any_printed = False

    for pos in positions:
        unrealized = float(pos.get("unrealizedPL", 0))
        if unrealized == 0:
            continue

        any_printed = True
        symbol  = pos.get("symbol")
        side    = pos.get("holdSide", "UNKNOWN")
        entry   = float(pos.get("entryPrice", 0))
        current = float(pos.get("marketPrice", 0))
        krw     = int(unrealized * rate)

        print(f"📌 종목: {symbol} | 방향: {side.upper()}")
        print(f"  진입가: {entry:.4f} | 현재가: {current:.4f}")
        print(f"  미실현 수익: {'+' if unrealized>=0 else ''}${unrealized:.2f}  (한화 약 {krw:,}원)\n")
        if unrealized > 0:
            print("  ✅ 현재 수익 중입니다!\n")
        else:
            print("  ⚠️ 손실 상태입니다. 전략 점검이 필요해요.\n")

    if not any_printed:
        print("✅ 포지션은 있으나, 미실현 손익이 0인 포지션만 있습니다.")

if __name__ == "__main__":
    main()
