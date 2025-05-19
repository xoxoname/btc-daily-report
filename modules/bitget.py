import os
import requests
import time
import hmac
import hashlib
import base64

BITGET_API_URL = "https://api.bitget.com/api/mix/v1/account/accounts"
BITGET_APIKEY = os.getenv("BITGET_APIKEY")
BITGET_APISECRET = os.getenv("BITGET_APISECRET")
BITGET_PASSPHRASE = os.getenv("BITGET_PASSPHRASE")

def get_bitget_signature(timestamp, method, request_path, body=""):
    prehash = str(timestamp) + method + request_path + body
    secret = BITGET_APISECRET.encode()
    return base64.b64encode(
        hmac.new(secret, prehash.encode(), hashlib.sha256).digest()
    ).decode()

def get_bitget_headers(method, path, body=""):
    timestamp = str(int(time.time() * 1000))
    sign = get_bitget_signature(timestamp, method, path, body)
    return {
        "ACCESS-KEY": BITGET_APIKEY,
        "ACCESS-SIGN": sign,
        "ACCESS-TIMESTAMP": timestamp,
        "ACCESS-PASSPHRASE": BITGET_PASSPHRASE,
        "Content-Type": "application/json"
    }

def get_futures_account(symbol="BTCUSDT_UMCBL"):
    # Bitget USDT-M Perpetual 계정/포지션 정보 가져오기
    try:
        path = f"/api/mix/v1/position/singlePosition"
        url = "https://api.bitget.com" + path
        params = {"symbol": symbol, "marginCoin": "USDT"}
        headers = get_bitget_headers("GET", path)
        resp = requests.get(url, headers=headers, params=params)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("data"):
                return data["data"]
            else:
                return {"error": "No data"}
        return {"error": f"API error: {resp.text}"}
    except Exception as e:
        return {"error": str(e)}

def get_asset_balance():
    try:
        path = "/api/mix/v1/account/accounts"
        url = "https://api.bitget.com" + path
        params = {"productType": "UMCBL"}
        headers = get_bitget_headers("GET", path)
        resp = requests.get(url, headers=headers, params=params)
        if resp.status_code == 200:
            return resp.json()
        return {"error": f"API error: {resp.text}"}
    except Exception as e:
        return {"error": str(e)}

# 진단 함수
def test_bitget_api():
    account = get_futures_account()
    asset = get_asset_balance()
    if isinstance(account, dict) and "error" in account:
        return f"❌ Bitget 계정 연동 오류: {account['error']}"
    if isinstance(asset, dict) and "error" in asset:
        return f"❌ Bitget 자산 연동 오류: {asset['error']}"
    return "✅ Bitget API 연동 정상"
