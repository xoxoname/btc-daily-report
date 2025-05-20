import os
import time
import requests
import base64
import hmac

API_KEY = os.getenv("BITGET_APIKEY")
API_SECRET = os.getenv("BITGET_APISECRET")
API_PASSPHRASE = os.getenv("BITGET_PASSPHRASE")

def bitget_signature(timestamp, method, path, body):
    prehash = f"{timestamp}{method}{path}{body}"
    sign = hmac.new(API_SECRET.encode(), prehash.encode(), digestmod='sha256').digest()
    return base64.b64encode(sign).decode()

def get_headers(method, path, body=""):
    timestamp = str(int(time.time() * 1000))
    sign = bitget_signature(timestamp, method, path, body)
    return {
        "ACCESS-KEY": API_KEY,
        "ACCESS-SIGN": sign,
        "ACCESS-TIMESTAMP": timestamp,
        "ACCESS-PASSPHRASE": API_PASSPHRASE,
        "Content-Type": "application/json"
    }

def get_usdt_futures_account():
    path = "/api/v2/mix/account/accounts"
    url = f"https://api.bitget.com{path}?productType=USDT-FUTURES"
    headers = get_headers("GET", path, "")
    resp = requests.get(url, headers=headers)
    try:
        data = resp.json()
        if "data" in data and isinstance(data["data"], dict):
            return data["data"]  # 실제 계좌 정보 반환
        else:
            return None
    except Exception as e:
        return None

# 포지션도 필요하면 아래처럼 별도 함수 추가
def get_positions(symbol="BTCUSDT"):
    path = "/api/v2/mix/position/single-position"
    url = f"https://api.bitget.com{path}?symbol={symbol}&productType=USDT-FUTURES"
    headers = get_headers("GET", path, "")
    resp = requests.get(url, headers=headers)
    try:
        data = resp.json()
        if "data" in data and data["data"]:
            return data["data"]
        else:
            return None
    except Exception as e:
        return None
