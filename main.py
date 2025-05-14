import os
import time
import json
import hmac
import hashlib
import requests
from datetime import datetime, timedelta, timezone

# 환경변수에서 읽어옵니다 (Render의 Environment Variables에 등록한 값)
API_KEY    = os.getenv("BITGET_API_KEY")
SECRET_KEY = os.getenv("BITGET_SECRET_KEY")
PASSPHRASE = os.getenv("BITGET_PASSPHRASE")

BASE_URL = "https://api.bitget.com"

def _sign(method: str, request_path: str, timestamp: str, body: str = "") -> str:
    """
    Bitget REST API 서명 생성
    """
    message = timestamp + method.upper() + request_path + body
    return hmac.new(SECRET_KEY.encode(), message.encode(), hashlib.sha256).hexdigest()

def _request(method: str, path: str, params: dict = None) -> requests.Response:
    """
    서명 포함 요청 전송
    """
    timestamp = str(int(time.time() * 1000))
    body = ""
    if method.upper() in ("POST", "PUT") and params:
        body = json.dumps(params)
    sign = _sign(method, path, timestamp, body)
    headers = {
        "ACCESS-KEY": API_KEY,
        "ACCESS-SIGN": sign,
        "ACCESS-TIMESTAMP": timestamp,
        "ACCESS-PASSPHRASE": PASSPHRASE,
        "Content-Type": "application/json",
    }
    url = BASE_URL + path
    return requests.request(method, url, headers=headers, params=params if method.upper()=="GET" else None, data=body or None, timeout=10)

def fetch_today_pnl(symbol: str = "BTCUSDT_UMCBL", margin_coin: str = "USDT") -> float:
    """
    오늘(UTC 기준) 실현 PNL 합계 조회
    """
    now = datetime.now(timezone.utc)
    start_of_day = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
    params = {
        "symbol": symbol,
        "marginCoin": margin_coin,
        "startTime": int(start_of_day.timestamp() * 1000),
        "endTime":   int(now.timestamp() * 1000),
        "pageSize":  50
    }
    resp = _request("GET", "/api/mix/v1/account/accountBill", params)
    resp.raise_for_status()
    data = resp.json().get("data", [])
    return sum(float(x.get("realizedPnl", 0)) for x in data)

def fetch_open_positions(product_type: str = "UMCBL", margin_coin: str = "USDT") -> list:
    """
    현재 열린 포지션 리스트 조회
    """
    params = {
        "productType": product_type,
        "marginCoin":  margin_coin,
    }
    resp = _request("GET", "/api/mix/v1/position/all-position", params)
    resp.raise_for_status()
    return resp.json().get("data", [])

def main():
    # 한국시간으로 출력
    now = datetime.now(timezone(timedelta(hours=9)))
    print(f"✅ [BTC 실시간 리포트] {now.strftime('%Y-%m-%d %H:%M:%S')}")
    print("-" * 40)

    # 1) 오늘 실현 PNL
    try:
        pnl = fetch_today_pnl()
        print(f"📊 오늘 실현 PNL: {pnl:.4f} USDT")
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
                qty   = float(p.get("holdingQty", 0))
                entry = float(p.get("avgEntryPrice", 0))
                print(f"▷ {sym} | 미실현 PNL: {upnl:.4f} USDT | 수량: {qty} | 진입가: {entry}")
    except Exception as e:
        print(f"❌ 실시간 포지션 조회 실패: {e}")

if __name__ == "__main__":
    main()

