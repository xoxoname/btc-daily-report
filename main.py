# main.py

import os
import time
import hmac
import hashlib
import requests
from datetime import datetime, timezone, timedelta

# 환경변수에서 키를 읽어옵니다 (Render의 Environment Variables 에 설정된 값)
API_KEY     = os.environ.get("BITGET_API_KEY")
SECRET_KEY  = os.environ.get("BITGET_SECRET_KEY")
PASSPHRASE  = os.environ.get("BITGET_PASSPHRASE")

BASE_URL = "https://api.bitget.com"

def _sign(timestamp: str, method: str, request_path: str, body: str = "") -> str:
    message = timestamp + method.upper() + request_path + body
    h = hmac.new(SECRET_KEY.encode(), message.encode(), hashlib.sha256)
    return h.hexdigest()

def _request(method: str, path: str, params: dict = None, body: dict = None):
    timestamp = str(int(time.time() * 1000))
    request_path = path + (("?" + "&".join(f"{k}={v}" for k,v in params.items())) if params else "")
    body_str = "" if not body else requests.utils.json.dumps(body)
    signature = _sign(timestamp, method, path, body_str)
    headers = {
        "ACCESS-KEY": API_KEY,
        "ACCESS-TIMESTAMP": timestamp,
        "ACCESS-PASSPHRASE": PASSPHRASE,
        "Content-Type": "application/json",
        "ACCESS-SIGN": signature,
    }
    url = BASE_URL + path
    r = requests.request(method, url, params=params, json=body, headers=headers, timeout=10)
    r.raise_for_status()
    return r

def fetch_today_pnl():
    """오늘 실현 PNL 조회"""
    now = datetime.now(timezone.utc)
    start = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
    params = {
        "productType": "UMCBL",
        "marginCoin": "USDT",
        "startTime": int(start.timestamp() * 1000),
        "endTime": int(now.timestamp() * 1000),
        "pageSize": 50
    }
    r = _request("GET", "/api/mix/v1/account/getAccountBill", params)
    data = r.json().get("data", [])
    return sum(item.get("realizedPnl", 0) for item in data)

def fetch_open_positions():
    """실시간 미실현 PNL (열려있는 포지션) 조회"""
    params = {
        "productType": "UMCBL",
        "marginCoin": "USDT"
    }
    r = _request("GET", "/api/mix/v1/position/get-open-positions", params)
    return r.json().get("data", [])

def main():
    # 타임스탬프 (한국시간)
    now_kst = datetime.now(timezone.utc) + timedelta(hours=9)
    print(f"\n✅ [BTC 실시간 리포트] {now_kst.strftime('%Y-%m-%d %H:%M:%S')}")
    print("-" * 40)

    # 1) 오늘 실현 수익
    try:
        pnl = fetch_today_pnl()
        print(f"💰 오늘 실현 PNL: {pnl:.4f} USDT")
    except Exception as e:
        print(f"❌ 오늘 수익 데이터 조회 실패: {e}")

    # 2) 실시간 미실현 PNL
    try:
        positions = fetch_open_positions()
        if not positions:
            print("📭 현재 열린 포지션이 없습니다.")
        else:
            for p in positions:
                sym   = p.get("symbol")
                upnl  = float(p.get("unrealizedProfit", 0))
                amt   = float(p.get("holdingQty", 0))
                entry = float(p.get("avgEntryPrice", 0))
                print(f"📈 {sym} | 미실현 PNL: {upnl:.4f} USDT | 수량: {amt} | 진입가: {entry}")
    except Exception as e:
        print(f"❌ 실시간 포지션 조회 실패: {e}")

if __name__ == "__main__":
    main()

