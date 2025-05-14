import os, time, hmac, hashlib, base64, requests
from datetime import datetime
from pytz import timezone
from dotenv import load_dotenv

load_dotenv()

API_KEY    = os.getenv("BITGET_API_KEY")
SECRET_KEY = os.getenv("BITGET_SECRET_KEY")
PASSPHRASE = os.getenv("BITGET_PASSPHRASE")
BASE_URL   = "https://api.bitget.com"

def sign(timestamp: str, method: str, request_path: str, body: str = "") -> str:
    message = f"{timestamp}{method}{request_path}{body}"
    mac = hmac.new(SECRET_KEY.encode(), message.encode(), hashlib.sha256)
    return base64.b64encode(mac.digest()).decode()

def headers_for(method: str, path: str, body: str = "") -> dict:
    ts = str(int(time.time() * 1000))
    return {
        "ACCESS-KEY":       API_KEY,
        "ACCESS-SIGN":      sign(ts, method, path, body),
        "ACCESS-TIMESTAMP": ts,
        "ACCESS-PASSPHRASE":PASSPHRASE,
        "Content-Type":     "application/json"
    }

def fetch_open_positions():
    path   = "/api/mix/v1/position/openPositions"
    params = "?productType=USDT-FUTURES&marginCoin=USDT"
    url    = BASE_URL + path + params
    resp   = requests.get(url, headers=headers_for("GET", path))
    resp.raise_for_status()
    return resp.json().get("data", [])

def main():
    now = datetime.now(timezone("Asia/Seoul")).strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n📈 실시간 포지션 수익 요약 — {now}\n")

    pos = fetch_open_positions()
    if not pos:
        print("📭 현재 보유 중인 open 포지션이 없습니다.")
        return

    rate = 1335
    for p in pos:
        sym   = p["symbol"]
        side  = p["holdSide"]
        entry = float(p["entryPrice"])
        mark  = float(p["marketPrice"])
        unreal = float(p["unrealizedPL"])
        krw    = int(unreal * rate)
        sign   = "+" if unreal>=0 else ""
        print(f"• {sym} | {side} | 진입 {entry:.2f} → {mark:.2f}")
        print(f"  미실현 PnL: {sign}${unreal:.2f} ({krw:,}원)\n")

if __name__ == "__main__":
    main()
