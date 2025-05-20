import os
import timeimport os
import time
import requests
import hmac
import hashlib
import base64

BITGET_APIKEY = os.environ.get('BITGET_APIKEY')
BITGET_APISECRET = os.environ.get('BITGET_APISECRET')
BITGET_PASSPHRASE = os.environ.get('BITGET_PASSPHRASE')

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
    response = requests.get(url, headers=headers)
    return response.json()

if __name__ == "__main__":
    print("APIKEY:", repr(BITGET_APIKEY))
    print("APISECRET:", repr(BITGET_APISECRET))
    print("PASSPHRASE:", repr(BITGET_PASSPHRASE))
    result = get_bitget_accounts()
    print("Bitget API 응답:", result)
