import os
import time
import hmac
import hashlib
import base64
import requests

BITGET_APIKEY = os.environ.get("BITGET_APIKEY")
BITGET_APISECRET = os.environ.get("BITGET_APISECRET")
BITGET_PASSPHRASE = os.environ.get("BITGET_PASSPHRASE")

BASE_URL = "https://api.bitget.com"

def _get_timestamp():
    return str(int(time.time() * 1000))

def _sign(method, endpoint, timestamp, body=""):
    message = timestamp + method.upper() + endpoint + body
    mac = hmac.new(BITGET_APISECRET.encode(), msg=message.encode(), digestmod=hashlib.sha256)
    return base64.b64encode(mac.digest()).decode()

def _get_headers(method, endpoint, body=""):
    timestamp = _get_timestamp()
    sign = _sign(method, endpoint, timestamp, body)
    return {
        "ACCESS-KEY": BITGET_APIKEY,
        "ACCESS-SIGN": sign,
        "ACCESS-TIMESTAMP": timestamp,
        "ACCESS-PASSPHRASE": BITGET_PASSPHRASE,
        "Content-Type": "application/json"
    }

def fetch_bitget_wallet_balance():
    endpoint = "/api/v2/account/assets"
    url = BASE_URL + endpoint
    headers = _get_headers("GET", endpoint)
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        usdt = next((item for item in data['data'] if item['coin'] == 'USDT'), {})
        total = float(usdt.get('available', 0)) + float(usdt.get('frozen', 0))
        available = float(usdt.get('available', 0))
        return {"total": total, "available": available}
    except Exception as e:
        print(f"[Wallet Error] {e}")
        return {"total": 0, "available": 0}

def fetch_bitget_positions():
    endpoint = "/api/mix/v1/position/singlePosition"
    url = BASE_URL + endpoint
    params = {
        "symbol": "BTCUSDT",
        "marginCoin": "USDT"
    }
    query = f"?symbol={params['symbol']}&marginCoin={params['marginCoin']}"
    headers = _get_headers("GET", endpoint + query)
    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        data = response.json()
        if "data" in data and isinstance(data["data"], dict):
            return [data["data"]]
        return []
    except Exception as e:
        print(f"[Position Error] {e}")
        return []
