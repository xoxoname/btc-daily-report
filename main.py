import os, time, hmac, hashlib, base64, requests
from datetime import datetime
from pytz import timezone
from dotenv import load_dotenv

load_dotenv()

API_KEY    = os.getenv("BITGET_API_KEY")
SECRET_KEY = os.getenv("BITGET_SECRET_KEY")
PASSPHRASE = os.getenv("BITGET_PASSPHRASE")
BASE_URL   = "https://api.bitget.com"

def sign(ts: str, method: str, path: str, body: str="") -> str:
    msg = f"{ts}{method}{path}{body}"
    mac = hmac.new(SECRET_KEY.encode(), msg.encode(), hashlib.sha256)
    return base64.b64encode(mac.digest()).decode()

def headers_for(method: str, path: str, body: str="") -> dict:
    ts = str(int(time.time()*1000))
    return {
        "ACCESS-KEY":        API_KEY,
        "ACCESS-SIGN":       sign(ts, method, path, body),
        "ACCESS-TIMESTAMP":  ts,
        "ACCESS-PASSPHRASE": PASSPHRASE,
        "Content-Type":      "application/json"
    }

def fetch_all_positions():
    # v2 엔드포인트, productType=UMCBL (USDT-마진 계약)
    path   = "/api/v2/mix/position/all-position"
    params = "?productType=UMCBL&marginCoin=USDT"
    url    = BASE_URL + path + params
    resp   = requests.get(url, headers=headers_for("GET", path))
    resp.raise_for_status()
    return resp.json().get("data", [])

def fetch_single_position(symbol: str):
    # 단일 심볼 조회, symbol 에는 _UMCBL 을 꼭 붙여야 합니다
    path   = "/api/v2/mix/position/single-position"
    params = f"?symbol={symbol}&marginCoin=USDT"
    url    = BASE_URL + path + params
    resp   = requests.get(url, headers=headers_for("GET", path))
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.json().get("data")

def main():
    now = datetime.now(timezone("Asia/Seoul")).strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n📈 실시간 포지션 수익 요약 — {now}\n")

    all_pos = fetch_all_positions()
    if not all_pos:
        print("📭 현재 보유 중인 open 포지션이 없습니다.")
        return

    rate = 1335
    for p in all_pos:
        sym_contract = p["symbol"]               # e.g. "BTCUSDT_UMCBL"
        detail       = fetch_single_position(sym_contract)
        if not detail: 
            continue

        entry   = float(detail["entryPrice"])
        mark    = float(detail["marketPrice"])
        unreal  = float(detail["unrealizedPL"])
        krw     = int(unreal * rate)
        sign    = "+" if unreal >= 0 else ""
        print(f"• {sym_contract} | {detail['holdSide']} | 진입 {entry:.2f} → 현재 {mark:.2f}")
        print(f"  미실현 PnL: {sign}${unreal:.2f} ({krw:,}원)\n")

if __name__ == "__main__":
    main()
