import os
import time
import hmac
import hashlib
import requests

BITGET_APIKEY = os.environ.get('BITGET_APIKEY')
BITGET_APISECRET = os.environ.get('BITGET_APISECRET')
BITGET_PASSPHRASE = os.environ.get('BITGET_PASSPHRASE')

def get_signature(ts, method, path, body, secret):
    prehash = f"{ts}{method.upper()}{path}{body}"
    sign = hmac.new(secret.encode('utf-8'), prehash.encode('utf-8'), hashlib.sha256).hexdigest()
    return sign

def get_headers(method, path, body=""):
    ts = str(int(time.time() * 1000))
    sign = get_signature(ts, method, path, body, BITGET_APISECRET)
    return {
        "ACCESS-KEY": BITGET_APIKEY,
        "ACCESS-SIGN": sign,
        "ACCESS-TIMESTAMP": ts,
        "ACCESS-PASSPHRASE": BITGET_PASSPHRASE,
        "Content-Type": "application/json"
    }

def get_accounts():
    method = "GET"
    path = "/api/v2/mix/account/accounts?productType=USDT-FUTURES"
    url = "https://api.bitget.com" + path
    headers = get_headers(method, path, "")
    print("==== REQUEST ====")
    print("KEY:", BITGET_APIKEY)
    print("SECRET:", BITGET_APISECRET)
    print("PASSPHRASE:", BITGET_PASSPHRASE)
    print("URL:", url)
    print("HEADERS:", headers)
    resp = requests.get(url, headers=headers)
    print("==== RESPONSE ====")
    print(resp.status_code)
    print(resp.text)
    return resp.text

if __name__ == "__main__":
    get_accounts()
