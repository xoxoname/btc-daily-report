import os
import requests
import time
import hmac
import hashlib
import base64

API_KEY = os.environ.get("BITGET_APIKEY")
API_SECRET = os.environ.get("BITGET_APISECRET")
PASSPHRASE = os.environ.get("BITGET_PASSPHRASE")

timestamp = str(int(time.time() * 1000))
method = "GET"
request_path = "/api/v2/mix/account/accounts"
query = "productType=USDT-FUTURES"
body = ""

pre_hash = f"{timestamp}{method}{request_path}?{query}{body}"

signature = base64.b64encode(
    hmac.new(API_SECRET.encode('utf-8'), pre_hash.encode('utf-8'), digestmod=hashlib.sha256).digest()
).decode()

headers = {
    "ACCESS-KEY": API_KEY,
    "ACCESS-SIGN": signature,
    "ACCESS-TIMESTAMP": timestamp,
    "ACCESS-PASSPHRASE": PASSPHRASE,
    "Content-Type": "application/json",
}

url = f"https://api.bitget.com{request_path}?{query}"
print("pre_hash:", pre_hash)
print("signature:", signature)
print("headers:", headers)
print("url:", url)

response = requests.get(url, headers=headers)
print("Status:", response.status_code)
print("Text:", response.text)
