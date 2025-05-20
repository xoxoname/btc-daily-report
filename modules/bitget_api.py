import os
import requests
import time
import base64
import hmac

BITGET_APIKEY = os.environ.get("BITGET_APIKEY")
BITGET_APISECRET = os.environ.get("BITGET_APISECRET")
BITGET_PASSPHRASE = os.environ.get("BITGET_PASSPHRASE")

def get_timestamp():
    return str(int(time.time() * 1000))

def sign_bitget(timestamp, method, path, body):
    msg = f"{timestamp}{method.upper()}{path}{body}"
    signature = hmac.new(
        BITGET_APISECRET.encode('utf-8'),
        msg.encode('utf-8'),
        digestmod='sha256'
    ).digest()
    return base64.b64encode(signature).decode()

def bitget_headers(method, path, body=""):
    ts = get_timestamp()
    sign = sign_bitget(ts, method, path, body)
    return {
        "ACCESS-KEY": BITGET_APIKEY,
        "ACCESS-SIGN": sign,
        "ACCESS-TIMESTAMP": ts,
        "ACCESS-PASSPHRASE": BITGET_PASSPHRASE,
        "Content-Type": "application/json"
    }

def test_bitget_account():
    # 계좌 조회 (GET)
    path = "/api/v2/mix/account/accounts"
    url = f"https://api.bitget.com{path}?productType=USDT-FUTURES"
    headers = bitget_headers("GET", path)
    resp = requests.get(url, headers=headers)
    print("Status:", resp.status_code)
    print("Resp:", resp.text)
    return resp.json()

if __name__ == "__main__":
    result = test_bitget_account()
    print(result)
