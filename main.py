import os
import requests
import time
import hmac
import hashlib
from datetime import datetime
from pytz import timezone
from dotenv import load_dotenv

load_dotenv()

API_KEY    = os.getenv("BITGET_API_KEY")
SECRET_KEY = os.getenv("BITGET_SECRET_KEY")
PASSPHRASE = os.getenv("BITGET_PASSPHRASE")
BASE_URL   = "https://api.bitget.com"

def get_timestamp():
    return str(int(time.time() * 1000))

def sign(message: str, secret_key: str):
    return hmac.new(secret_key.encode(), message.encode(), hashlib.sha256).hexdigest()

def fetch_all_positions():
    # v1 엔드포인트 사용 (v2 가 아니라 v1)
    path  = "/api/mix/v1/position/all-position"
    params = {
        "productType": "USDT-FUTURES",
        "marginCoin":  "USDT"
    }
    query = "&".join([f"{k}={v}" for k,v in params.items()])
    ts    = get_timestamp()
    to_sign   = f"{ts}GET{path}?{query}"
    signature = sign(to_sign, SECRET_KEY)

    headers = {
        "ACCESS-KEY":        API_KEY,
        "ACCESS-SIGN":       signature,
        "ACCESS-TIMESTAMP":  ts,
        "ACCESS-PASSPHRASE": PASSPHRASE,
        "Content-Type":      "application/json"
    }
    url = f"{BASE_URL}{path}?{query}"

    # —— 디버그 로그 시작 —— 
    print("▶️ REQUEST URL   :", url)
    print("▶️ ACCESS-TIMESTAMP:", ts)
    print("▶️ SIGNATURE     :", signature)
    print("▶️ HEADERS       :", {k: headers[k] for k in headers if k != "ACCESS-SIGN"})
    # —— 디버그 로그 끝 ——

    resp = requests.get(url, headers=headers)
    try:
        resp.raise_for_status()
        return resp.json().get("data", [])
    except requests.HTTPError:
        print("❌ STATUS CODE:", resp.status_code)
        print("❌ RESPONSE BODY:", resp.text)
        return []

def main():
    now = datetime.now(timezone("Asia/Seoul")).strftime("%Y-%m-%d %H:%M:%S")
    positions = fetch_all_positions()

    print("\n📈 [실시간 포지션 수익 요약]")
    print(f"시각: {now}\n")

    if not positions:
        print("📭 현재 보유 중인 포지션이 없습니다.")
        return

    rate = 1335
    reported = False

    for pos in positions:
        unreal = float(pos.get("unrealizedPL", 0))
        if unreal == 0: continue
        reported = True

        sym   = pos["symbol"]
        side  = pos["holdSide"]
        entry = float(pos["entryPrice"])
        mkt   = float(pos["marketPrice"])
        krw   = int(unreal * rate)

        print(f"📌 {sym} | {side} | 진입 {entry:.2f} → 현재 {mkt:.2f}")
        print(f"   미실현 PnL: {'+' if unreal>=0 else ''}${unreal:.2f} ({krw:,}원)\n")

    if not reported:
        print("✅ 포지션은 있으나, 미실현 손익이 0인 포지션만 있습니다.")

if __name__ == "__main__":
    main()
