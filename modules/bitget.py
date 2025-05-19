import os
import requests
import time
import hmac
import hashlib
import base64

BITGET_APIKEY = os.getenv("BITGET_APIKEY")
BITGET_APISECRET = os.getenv("BITGET_APISECRET")
BITGET_PASSPHRASE = os.getenv("BITGET_PASSPHRASE")

BASE_URL = "https://api.bitget.com/api/mix/v1"

def _signature(timestamp, method, request_path, body):
    message = f"{timestamp}{method}{request_path}{body}"
    mac = hmac.new(BITGET_APISECRET.encode(), message.encode(), hashlib.sha256)
    return base64.b64encode(mac.digest()).decode()

def _headers(method, path, body=""):
    timestamp = str(int(time.time() * 1000))
    sign = _signature(timestamp, method, path, body)
    return {
        "ACCESS-KEY": BITGET_APIKEY,
        "ACCESS-SIGN": sign,
        "ACCESS-TIMESTAMP": timestamp,
        "ACCESS-PASSPHRASE": BITGET_PASSPHRASE,
        "Content-Type": "application/json"
    }

def get_positions():
    path = "/position/singlePosition"
    url = f"{BASE_URL}{path}?symbol=BTCUSDT&marginCoin=USDT"
    r = requests.get(url, headers=_headers("GET", path))
    try:
        data = r.json()
        if data["code"] == "00000":
            pos = data["data"]
            return {
                "symbol": pos["symbol"],
                "side": pos["holdSide"].capitalize(),
                "openPrice": float(pos["openPrice"]),
                "currentPrice": float(pos["latestPrice"]),
                "leverage": float(pos["leverage"]),
                "liquidationPrice": float(pos["liquidationPrice"]),
                "positionAmt": float(pos["total"]),
                "unrealizedPnl": float(pos["unrealizedPL"]),
                "margin": float(pos["margin"]),
            }
        else:
            return None
    except Exception as e:
        return None

def get_wallet():
    # Bitget API 계정 자산 조회 (USDT만 예시)
    url = "https://api.bitget.com/api/spot/v1/account/assets"
    r = requests.get(url, headers=_headers("GET", "/account/assets"))
    try:
        data = r.json()
        usdt = next(x for x in data["data"] if x["coinName"] == "USDT")
        return float(usdt["available"])
    except Exception as e:
        return 0.0
