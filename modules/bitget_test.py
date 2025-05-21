import os
import time
import hmac
import base64
import requests

key = os.environ.get('BITGET_APIKEY')
secret = os.environ.get('BITGET_APISECRET')
passphrase = os.environ.get('BITGET_PASSPHRASE')

print("BITGET_APIKEY:", repr(key))
print("BITGET_APISECRET:", repr(secret))
print("BITGET_PASSPHRASE:", repr(passphrase))

timestamp = str(int(time.time() * 1000))
method = "GET"
path = "/api/v2/mix/account/accounts"
body = ""
prehash = f"{timestamp}{method}{path}{body}"
print("Prehash:", repr(prehash))
sign = hmac.new(secret.encode(), prehash.encode(), digestmod='sha256').digest()
signature = base64.b64encode(sign).decode()
print("SIGNATURE:", repr(signature))

headers = {
    "ACCESS-KEY": key,
    "ACCESS-SIGN": signature,
    "ACCESS-TIMESTAMP": timestamp,
    "ACCESS-PASSPHRASE": passphrase,
    "Content-Type": "application/json"
}
print("HEADERS:", headers)

url = "https://api.bitget.com/api/v2/mix/account/accounts?productType=USDT-FUTURES"
resp = requests.get(url, headers=headers)
print("STATUS:", resp.status_code)
print("RESPONSE:", resp.text)
