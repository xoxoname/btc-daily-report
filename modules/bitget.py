import os
import time
import requests
import hmac
import hashlib
import base64

# 환경 변수에서 키값 로딩 (Render 환경변수 사용)
BITGET_APIKEY = os.environ.get('BITGET_APIKEY')
BITGET_APISECRET = os.environ.get('BITGET_APISECRET')
BITGET_PASSPHRASE = os.environ.get('BITGET_PASSPHRASE')

def get_bitget_signature(timestamp, method, request_path, body, secret):
    # prehash 포맷(문서 기준)
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
    body = ""  # GET은 body 없음
    headers = get_bitget_headers(method, request_path, body)
    response = requests.get(url, headers=headers)
    return response.json()

if __name__ == "__main__":
    print("APIKEY:", repr(BITGET_APIKEY))
    print("APISECRET:", repr(BITGET_APISECRET))
    print("PASSPHRASE:", repr(BITGET_PASSPHRASE))
    print("응답:", get_bitget_accounts())
