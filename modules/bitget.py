import os
import time
import requests
import hmac
import hashlib
import base64
import json

BITGET_APIKEY = os.environ.get('BITGET_APIKEY')
BITGET_APISECRET = os.environ.get('BITGET_APISECRET')
BITGET_PASSPHRASE = os.environ.get('BITGET_PASSPHRASE')

def get_bitget_signature(timestamp, method, request_path, body, secret):
    # Bitget 공식 문서: sign = HMAC_SHA256(timestamp + method + request_path + body, secretKey), Base64 인코딩
    prehash = f"{timestamp}{method}{request_path}{body}"
    sign = hmac.new(secret.encode('utf-8'), prehash.encode('utf-8'), hashlib.sha256).digest()
    return base64.b64encode(sign).decode()

def get_bitget_headers(method, request_path, body=""):
    timestamp = str(int(time.time() * 1000))
    signature = get_bitget_signature(timestamp, method.upper(), request_path, body, BITGET_APISECRET)
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
    response = requests.get(url, headers=headers)
    return response.json()

if __name__ == "__main__":
    print("BITGET_APIKEY:", repr(BITGET_APIKEY))
    print("BITGET_APISECRET:", repr(BITGET_APISECRET))
    print("BITGET_PASSPHRASE:", repr(BITGET_PASSPHRASE))
    result = get_bitget_accounts()
    print("Bitget API 응답:", json.dumps(result, ensure_ascii=False, indent=2))
