import os
import time
import hmac
import hashlib
import json
import requests
from datetime import datetime, timezone, timedelta

# —— 설정 ——
API_KEY    = os.environ["BITGET_API_KEY"]
SECRET_KEY = os.environ["BITGET_SECRET_KEY"]
PASSPHRASE = os.environ["BITGET_PASSPHRASE"]
BASE_URL   = "https://api.bitget.com"

# —— 내부 함수들 ——
def _sign(timestamp: str, method: str, path: str, body: str = "") -> str:
    msg = f"{timestamp}{method.upper()}{path}{body}"
    return hmac.new(SECRET_KEY.encode(), msg.encode(), hashlib.sha256).hexdigest()

def _request(method: str, path: str, params: dict = None, body: dict = None) -> requests.Response:
    ts = str(int(time.time() * 1000))
    body_str = "" if body is None else json.dumps(body)
    signature = _sign(ts, method, path, body_str)
    headers = {
        "ACCESS-KEY": API_KEY,
        "ACCESS-TIMESTAMP": ts,
        "ACCESS-PASSPHRASE": PASSPHRASE,
        "ACCESS-SIGN": signature,
        "Content-Type": "application/json"
    }
    url = BASE_URL + path
    resp = requests.request(method, url, headers=headers, params=params, data=body_str)
    resp.raise_for_status()
    return resp

# —— 기능 함수들 ——
def fetch_today_pnl() -> float:
    """
    오늘(00:00~현재) 실현 PNL 합계를 가져옵니다.
    """
    now_ms   = int(time.time() * 1000)
    start_ms = int(
        datetime.now()
                .replace(hour=0, minute=0, second=0, microsecond=0)
                .timestamp()
        * 1000
    )
    params = {
        "productType": "USDT-Futures",
        "marginCoin":  "USDT",            # ← 여기에 marginCoin 추가
        "startTime":   start_ms,
        "endTime":     now_ms,
        "pageSize":    50
    }
    r = _request("get", "/api/mix/v1/account/accountBill", params=params)
    data = r.json().get("data", [])
    return sum(float(item.get("realizedPnl", 0)) for item in data)

def fetch_open_positions() -> list:
    """
    현재 열린 모든 포지션의 미실현 PNL 리스트를 가져옵니다.
    """
    params = {
        "productType": "USDT-Futures",
        "marginCoin":  "USDT"             # ← 여기도 marginCoin 추가
    }
    r = _request("get", "/api/mix/v1/position/allPositions", params=params)
    return r.json().get("data", [])

# —— 메인 ——
def main():
    now = datetime.now(timezone(timedelta(hours=9))).strftime("%Y-%m-%d %H:%M:%S")
    print(f"✅ [BTC 실시간 리포트] {now}")
    print("-" * 40)

    # 1) 오늘 실현 PNL
    try:
        pnl = fetch_today_pnl()
        print(f"▶ 오늘 실현 PNL: {pnl:.4f} USDT")
    except Exception as e:
        print(f"❌ 오늘 수익 데이터 조회 실패: {e}")

    # 2) 실시간 미실현 PNL
    try:
        positions = fetch_open_positions()
        if not positions:
            print("▶ 현재 열린 포지션이 없습니다.")
        else:
            for p in positions:
                sym   = p.get("symbol")
                upnl  = float(p.get("unrealizedProfit", 0))
                qty   = float(p.get("holdingQty", 0))
                entry = float(p.get("avgEntryPrice", 0))
                print(f"{sym} | 미실현 PNL: {upnl:.4f} USDT | 수량: {qty} | 진입가: {entry}")
    except Exception as e:
        print(f"❌ 실시간 포지션 조회 실패: {e}")

if __name__ == "__main__":
    main()
