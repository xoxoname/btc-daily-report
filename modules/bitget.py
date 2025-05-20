import time
import requests
import hmac
import hashlib
import base64
from .constants import BITGET_APIKEY, BITGET_APISECRET, BITGET_PASSPHRASE

def get_bitget_signature(timestamp, method, request_path, body, secret):
    prehash = f"{timestamp}{method.upper()}{request_path}{body}"
    sign = hmac.new(secret.encode('utf-8'), prehash.encode('utf-8'), hashlib.sha256).digest()
    return base64.b64encode(sign).decode()

def get_bitget_headers(method, request_path, body=""):
    timestamp = str(int(time.time() * 1000))
    signature = get_bitget_signature(timestamp, method, request_path, body, BITGET_APISECRET)
    return {
        "ACCESS-KEY": BITGET_APIKEY,
        "ACCESS-SIGN": signature,
        "ACCESS-TIMESTAMP": timestamp,
        "ACCESS-PASSPHRASE": BITGET_PASSPHRASE,
        "Content-Type": "application/json"
    }

def get_bitget_accounts():
    method = "GET"
    request_path = "/api/v2/mix/account/accounts?productType=USDT-FUTURES"
    url = "https://api.bitget.com" + request_path
    body = ""
    headers = get_bitget_headers(method, request_path, body)
    resp = requests.get(url, headers=headers)
    if resp.status_code != 200:
        return {"error": f"HTTP {resp.status_code}", "response": resp.text}
    data = resp.json()
    if "code" in data and data["code"] != "00000":
        return {"error": f'Bitget API 오류: {data}'}
    return data
