import os
import time
import hmac
import hashlib
import requests
from datetime import datetime, timezone, timedelta

# --- 환경 변수에서 키·시크릿·패스프레이즈 읽기 ---
API_KEY     = os.getenv("BITGET_API_KEY")
SECRET_KEY  = os.getenv("BITGET_SECRET_KEY")
PASSPHRASE  = os.getenv("BITGET_PASSPHRASE")

BASE_URL    = "https://api.bitget.com"

def _get_timestamp_ms():
    return str(int(time.time() * 1000))

def _sign(method: str, request_path: str, timestamp: str, body: str=""):
    """Bitget REST API HMAC-SHA256 서명 생성"""
    message = timestamp + method.upper() + request_path + body
    mac = hmac.new(SECRET_KEY.encode('utf-8'),
                   message.encode('utf-8'),
                   digestmod=hashlib.sha256)
    return mac.hexdigest()

def _request(method: str, path: str, params=None, body=None):
    ts = _get_timestamp_ms()
    body_str = "" if body is None else requests.utils.json.dumps(body)
    sign = _sign(method, path, ts, body_str)
    headers = {
        "Content-Type":   "application/json",
        "ACCESS-KEY":     API_KEY,
        "ACCESS-TIMESTAMP": ts,
        "ACCESS-PASSPHRASE": PASSPHRASE,
        "ACCESS-SIGN":    sign
    }
    url = BASE_URL + path
    if method.lower() == "get":
        return requests.get(url, headers=headers, params=params)
    else:
        return requests.post(url, headers=headers, json=body)

def fetch_today_pnl():
    """오늘(UTC+9) 수익 요약 조회"""
    # Bitget 선물 수익 내역 엔드포인트 v1 (UMCBL = USDT-Perpetual)
    path = "/api/mix/v1/account/accountBill"
    now = datetime.now(timezone(timedelta(hours=9)))
    start = datetime(now.year, now.month, now.day, tzinfo=now.tzinfo)
    # 밀리초 타임스탬프
    start_ts = int(start.timestamp() * 1000)
    end_ts   = int(now.timestamp() * 1000)
    params = {
        "productType": "UMCBL",
        "marginCoin":  "USDT",
        "startTime":   start_ts,
        "endTime":     end_ts,
        "pageSize":    50
    }
    r = _request("get", path, params=params)
    r.raise_for_status()
    data = r.json().get("data", [])
    pnl = sum(item.get("profit", 0) for item in data)
    return pnl

def fetch_open_positions():
    """실시간 미실현 PNL 조회 (열려있는 포지션만)"""
    # v2 open positions
    path = "/api/v2/mix/position/get-open-positions"
    params = {
        "productType": "UMCBL",
        "marginCoin":  "USDT"
    }
    r = _request("get", path, params=params)
    r.raise_for_status()
    positions = r.json().get("data", [])
    return positions

def main():
    now = datetime.now(timezone(timedelta(hours=9))).strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n📈 [BTC 실시간 리포트] {now}\n" + "-"*40)

    # 1) 오늘 수익
    try:
        pnl = fetch_today_pnl()
        print(f"▶ 오늘 실현 PNL: {pnl:.4f} USDT")
    except Exception as e:
        print(f"❌ 오늘 수익 데이터 조회 실패: {e}")

    # 2) 실시간 미실현 PNL
    try:
        pos = fetch_open_positions()
        if not pos:
            print("📭 현재 열린 포지션이 없습니다.")
        else:
            for p in pos:
                sym   = p.get("symbol")
                upnl  = float(p.get("unrealizedProfit", 0))
                amt   = float(p.get("holdingQty", 0))
                entry = float(p.get("avgEntryPrice", 0))
                print(f"• {sym} | 미실현 PNL: {upnl:.4f} USDT | 수량: {amt} | 진입가: {entry}")
    except Exception as e:
        print(f"❌ 실시간 포지션 조회 실패: {e}")

if __name__ == "__main__":
    main()
