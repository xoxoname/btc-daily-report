# main.py
import os
import time
import hmac
import hashlib
import requests
from datetime import datetime, timezone, timedelta

# Render 대시보드 → Environment → 아래 3개 키를 설정하세요.
API_KEY     = os.getenv("BITGET_API_KEY")
SECRET_KEY  = os.getenv("BITGET_SECRET_KEY")
PASSPHRASE  = os.getenv("BITGET_PASSPHRASE")

BASE_URL = "https://api.bitget.com"

def _sign(timestamp: str, method: str, request_path: str, body: str="") -> str:
    """
    Bitget 공통 HMAC-SHA256 시그니처 생성
    """
    message = f"{timestamp}{method}{request_path}{body}"
    return hmac.new(SECRET_KEY.encode(), message.encode(), hashlib.sha256).hexdigest()

def _request(method: str, path: str, params: dict=None, body: str="") -> requests.Response:
    """
    GET/POST 요청 래퍼
    """
    timestamp = str(int(time.time() * 1000))
    request_path = f"/api/mix/v1/{path}"
    signature = _sign(timestamp, method.upper(), request_path, body)
    headers = {
        "ACCESS-KEY": API_KEY,
        "ACCESS-TIMESTAMP": timestamp,
        "ACCESS-PASSPHRASE": PASSPHRASE,
        "Content-Type": "application/json",
        "X-ACCESS-SIGN": signature,
    }
    url = BASE_URL + request_path
    if method.lower() == "get":
        return requests.get(url, headers=headers, params=params)
    else:
        return requests.post(url, headers=headers, data=body)

def fetch_today_pnl() -> float:
    """
    오늘(UTC) 실현 PNL 합계 조회
    """
    now = datetime.now(timezone.utc)
    start_of_day = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
    params = {
        "productType": "UMCBL",      # USDT-M perpetual
        "marginCoin": "USDT",
        "startTime": int(start_of_day.timestamp() * 1000),
        "endTime":   int(now.timestamp() * 1000),
        "pageSize": 50
    }
    r = _request("get", "account/accountBill", params)
    r.raise_for_status()
    items = r.json().get("data", [])
    # 실제 필드 이름은 profitUsd, profit etc. 리턴 구조 확인 후 조정하세요
    return sum(float(item.get("profitUsd", 0)) for item in items)

def fetch_open_positions() -> list:
    """
    현재 열린 모든 포지션 조회
    """
    params = {"productType": "UMCBL", "marginCoin": "USDT"}
    r = _request("get", "position/openPositions", params)
    r.raise_for_status()
    return r.json().get("data", [])

def main():
    # 한국시간 출력
    now_kst = datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=9)))
    print(f"\n✅ [BTC 실시간 리포트] {now_kst.strftime('%Y-%m-%d %H:%M:%S')}\n" + "-"*40)

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
                unpl  = float(p.get("unrealizedProfit", 0))
                qty   = float(p.get("holdingQty", 0))
                entry = float(p.get("avgEntryPrice", 0))
                print(f"• {sym} | 미실현 PNL: {unpl:.4f} USDT | 수량: {qty} | 진입가: {entry}")
    except Exception as e:
        print(f"❌ 실시간 포지션 조회 실패: {e}")

if __name__ == "__main__":
    main()
