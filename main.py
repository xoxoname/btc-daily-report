import os
import time
import json
import hmac
import hashlib
import requests
from datetime import datetime, timezone, timedelta

# ─── 환경 변수 로드 (Render의 Environment Variables에서 설정) ─────────────────────────
API_KEY     = os.environ["BITGET_API_KEY"]
SECRET_KEY  = os.environ["BITGET_SECRET_KEY"]
PASSPHRASE  = os.environ["BITGET_PASSPHRASE"]
# ─────────────────────────────────────────────────────────────────────────────────────

BASE_URL = "https://api.bitget.com"

def sign(timestamp: str, method: str, request_path: str, body: str = "") -> str:
    """비밀키로 서명 생성"""
    message = timestamp + method.upper() + request_path + body
    mac = hmac.new(SECRET_KEY.encode(), message.encode(), hashlib.sha256)
    return mac.hexdigest()

def _request(method: str, path: str, params: dict = None):
    """공통 요청 함수 (GET/POST)"""
    ts = str(int(time.time() * 1000))
    rb = ""
    req_path = path

    if method.upper() == "GET" and params:
        qs = "&".join(f"{k}={v}" for k, v in params.items())
        req_path = f"{path}?{qs}"
    elif method.upper() in ("POST", "PUT") and params:
        rb = json.dumps(params)

    signature = sign(ts, method, req_path, rb)
    headers = {
        "ACCESS-KEY": API_KEY,
        "ACCESS-SIGN": signature,
        "ACCESS-TIMESTAMP": ts,
        "ACCESS-PASSPHRASE": PASSPHRASE,
        "Content-Type": "application/json"
    }

    url = BASE_URL + req_path
    resp = requests.request(method, url, headers=headers, data=rb)
    resp.raise_for_status()
    return resp.json()

def fetch_today_pnl():
    """오늘자 실현 PNL 합계 (accountBill)"""
    # 오늘 00:00(KST) 타임스탬프(ms)
    now = datetime.now(timezone(timedelta(hours=9)))
    start = datetime(now.year, now.month, now.day, tzinfo=timezone(timedelta(hours=9)))
    params = {
        "productType": "usdt-futures",  # 반드시 소문자
        "marginCoin":  "usdt",
        "startTime":   int(start.timestamp() * 1000),
        "endTime":     int(now.timestamp() * 1000),
        "pageSize":    50
    }
    data = _request("GET", "/api/mix/v1/account/accountBill", params)
    lst = data.get("data", [])
    # 'realizedPnl' 키로 실현 수익이 반환됨
    return sum(item.get("realizedPnl", 0) for item in lst)

def fetch_open_positions():
    """현재 열린 포지션들 (allPositions)"""
    params = {
        "productType": "usdt-futures",
        "marginCoin":  "usdt"
    }
    data = _request("GET", "/api/mix/v1/position/allPositions", params)
    return data.get("data", [])

def main():
    now = datetime.now(timezone(timedelta(hours=9))).strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n✅ [BTC 실시간 리포트] {now}\n" + "-"*40)

    # 1) 오늘 실현 PNL
    try:
        pnl = fetch_today_pnl()
        print(f"▶️ 오늘 실현 PNL: {pnl:.4f} USDT")
    except Exception as e:
        print(f"❌ 오늘 수익 데이터 조회 실패: {e}")

    # 2) 현재 미실현 PNL
    try:
        pos = fetch_open_positions()
        if not pos:
            print("📭 현재 열린 포지션이 없습니다.")
        else:
            print("📈 열린 포지션 수익 요약:")
            for p in pos:
                symbol = p.get("symbol")
                upnl   = float(p.get("unrealizedProfit", 0))
                amt    = float(p.get("holdingQty", 0))
                entry  = float(p.get("avgEntryPrice", 0))
                print(f"  • {symbol} | 미실현 PNL: {upnl:.4f} USDT | 수량: {amt} | 진입가: {entry}")
    except Exception as e:
        print(f"❌ 실시간 포지션 조회 실패: {e}")

if __name__ == "__main__":
    main()
