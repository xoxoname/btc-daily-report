import os
import time
import hmac
import json
import hashlib
import requests
from datetime import datetime
from dotenv import load_dotenv

# 1) .env 로딩
load_dotenv()

API_KEY    = os.getenv("BITGET_API_KEY")
SECRET_KEY = os.getenv("BITGET_SECRET_KEY").encode()
PASSPHRASE = os.getenv("BITGET_PASSPHRASE")

BASE = "https://api.bitget.com"

def _sign(path: str, method: str, body: str, timestamp: str) -> str:
    message = timestamp + method.upper() + path + body
    return hmac.new(SECRET_KEY, message.encode(), hashlib.sha256).hexdigest()

def _request(path: str, params=None, method="GET"):
    ts = str(int(time.time() * 1000))
    body = json.dumps(params or {}) if method=="POST" else ""
    full_path = path + (("?" + "&".join(f"{k}={v}" for k,v in params.items())) if params and method=="GET" else "")
    sign = _sign(path, method, body, ts)
    headers = {
        "ACCESS-KEY": API_KEY,
        "ACCESS-TIMESTAMP": ts,
        "ACCESS-PASSPHRASE": PASSPHRASE,
        "Content-Type": "application/json",
        "ACCESS-SIGN": sign
    }
    url = BASE + full_path
    r = requests.request(method, url, headers=headers, data=body or None)
    r.raise_for_status()
    return r.json()

def fetch_today_pnl():
    # UTC 기준 00:00 ~ now
    now = int(time.time() * 1000)
    today0 = int(datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0).timestamp()*1000)
    params = {
        "productType": "USDT-Perpetual",
        "startTime": today0,
        "endTime": now,
        "pageSize": 50
    }
    data = _request("/api/mix/v1/account/accountBill", params)
    pnl = sum(item.get("realProfit",0) for item in data.get("data", []))
    return pnl

def fetch_open_positions():
    # USDT-Perpetual 전체 오픈 포지션 조회
    params = {
        "productType": "USDT-Perpetual",
        "pageSize": 50
    }
    data = _request("/api/mix/v1/position/all-position", params)
    return data.get("data", [])

def main():
    # 1) 오늘 실현 PNL
    try:
        pnl = fetch_today_pnl()
        krw = pnl * 1330  # 달러당 환율 가정
        print(f"📈 [BTC 수익 요약]\n시각: {datetime.now()}\n수익: {pnl:+.2f} USD  한화 약 {krw:,.0f}원\n")
    except Exception as e:
        print("❌ 오늘 수익 데이터 조회 실패:", e)

    # 2) 실시간 미실현 PNL
    print("📈 [실시간 포지션 수익 요약]")
    try:
        pos = fetch_open_positions()
        if not pos:
            print("📭 현재 보유 중인 포지션이 없습니다.")
        else:
            for p in pos:
                sym = p["symbol"]
                upnl = float(p["unrealizedProfit"])
                print(f" - {sym}: {upnl:+.2f} USD")
    except Exception as e:
        print("❌ 포지션 조회 실패:", e)

if __name__ == "__main__":
    main()
