import os
import time
import hmac, hashlib, base64
import requests

API_KEY    = os.getenv("BITGET_API_KEY")
SECRET_KEY = os.getenv("BITGET_SECRET_KEY")
PASSPHRASE = os.getenv("BITGET_PASSPHRASE")
BASE_URL   = "https://api.bitget.com"

def _sign(timestamp, method, request_path, body=""):
    message = f"{timestamp}{method}{request_path}{body}"
    hmac_key = hmac.new(SECRET_KEY.encode(), message.encode(), hashlib.sha256)
    return base64.b64encode(hmac_key.digest()).decode()

def _headers(method, path, body=""):
    ts = str(int(time.time() * 1000))
    return {
        "ACCESS-KEY": API_KEY,
        "ACCESS-TIMESTAMP": ts,
        "ACCESS-PASSPHRASE": PASSPHRASE,
        "ACCESS-SIGN": _sign(ts, method, path, body),
        "Content-Type": "application/json"
    }

def fetch_all_positions():
    path   = "/api/mix/v1/position/allPositions"
    params = "?productType=USDT-FUTURES&marginCoin=USDT"
    url    = BASE_URL + path + params
    r = requests.get(url, headers=_headers("GET", path))
    r.raise_for_status()
    return r.json()["data"]

def fetch_single_position(symbol):
    path   = "/api/mix/v1/position/singlePosition"
    params = f"?symbol={symbol}&marginCoin=USDT"
    url    = BASE_URL + path + params
    r = requests.get(url, headers=_headers("GET", path))
    if r.status_code == 404:
        # 포지션이 없으면 404를 반환합니다.
        return None
    r.raise_for_status()
    return r.json()["data"]

if __name__ == "__main__":
    positions = fetch_all_positions()
    if not positions:
        print("📭 현재 보유 중인 포지션이 없습니다.")
    else:
        for pos in positions:
            sym = pos["symbol"]
            detail = fetch_single_position(sym)
            print(f"{sym} 포지션: {detail}")
