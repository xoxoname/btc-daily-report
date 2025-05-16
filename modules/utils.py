import requests
import time
import hmac
import hashlib
import base64
import os

BITGET_APIKEY = os.getenv("BITGET_APIKEY")
BITGET_SECRET = os.getenv("BITGET_SECRET")
BITGET_PASSPHRASE = os.getenv("BITGET_PASSPHRASE")

def fetch_bitget_position_data():
    url = "https://api.bitget.com/api/mix/v1/position/singlePosition"
    params = {
        "symbol": "BTCUSDT",
        "marginCoin": "USDT"
    }

    timestamp = str(int(time.time() * 1000))
    method = "GET"
    path = f"/api/mix/v1/position/singlePosition?symbol=BTCUSDT&marginCoin=USDT"
    pre_hash = timestamp + method + path
    sign = base64.b64encode(hmac.new(BITGET_SECRET.encode(), pre_hash.encode(), hashlib.sha256).digest()).decode()

    headers = {
        "ACCESS-KEY": BITGET_APIKEY,
        "ACCESS-SIGN": sign,
        "ACCESS-TIMESTAMP": timestamp,
        "ACCESS-PASSPHRASE": BITGET_PASSPHRASE
    }

    response = requests.get(url, headers=headers, params=params)
    data = response.json()

    if data.get("code") != "00000":
        return {"error": "API 응답 오류", "data": data}

    position = data["data"]
    return {
        "avg_entry_price": float(position["entryPrice"]),
        "unrealized_pnl": float(position["unrealizedPL"]),
        "position_amt": float(position["total"]),
    }
