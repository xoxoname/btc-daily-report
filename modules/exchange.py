import time
import hmac
import hashlib
import base64
import requests
import os

# 환경변수에서 안전하게 불러오기 (깃허브에는 노출 X)
API_KEY = os.environ.get("BITGET_APIKEY")
API_SECRET = os.environ.get("BITGET_APISECRET")
API_PASSPHRASE = os.environ.get("BITGET_PASSPHRASE")

def bitget_request(method, path, params=None, data=None):
    timestamp = str(int(time.time() * 1000))
    method = method.upper()

    if params and method == "GET":
        qs = "?" + "&".join([f"{k}={params[k]}" for k in sorted(params)])
        full_path = path + qs
        body = ""
    elif data and method == "POST":
        full_path = path
        body = data
    else:
        full_path = path
        body = ""

    # prehash: 쿼리스트링 붙이면 안됨!
    prehash = timestamp + method + path
    if method == "POST" and body:
        prehash += body

    sign = base64.b64encode(
        hmac.new(
            API_SECRET.encode('utf-8'),
            prehash.encode('utf-8'),
            digestmod=hashlib.sha256
        ).digest()
    ).decode()

    headers = {
        "ACCESS-KEY": API_KEY,
        "ACCESS-SIGN": sign,
        "ACCESS-TIMESTAMP": timestamp,
        "ACCESS-PASSPHRASE": API_PASSPHRASE,
        "Content-Type": "application/json"
    }
    url = "https://api.bitget.com" + path
    if method == "GET":
        resp = requests.get(url, headers=headers, params=params)
    elif method == "POST":
        resp = requests.post(url, headers=headers, data=body)
    else:
        raise ValueError("지원하지 않는 메서드")
    try:
        return resp.status_code, resp.json()
    except Exception as e:
        return resp.status_code, resp.text

# 아래는 연동 예시. 실제 봇에서 함수로 호출하여 사용.
def get_single_position(symbol="BTCUSDT_UMCBL", margin_coin="USDT"):
    path = "/api/mix/v1/position/singlePosition"
    params = {"symbol": symbol, "marginCoin": margin_coin}
    return bitget_request("GET", path, params=params)

def get_spot_balance():
    path = "/api/spot/v1/account/assets"
    return bitget_request("GET", path)
