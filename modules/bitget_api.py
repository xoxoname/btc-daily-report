import requests
import time
import hmac
import hashlib
import base64
import os

def get_env(key):
    v = os.environ.get(key, '').strip()
    print(f"[bitget_api] ENV {key} = [{v}]")
    return v

def sign_request(timestamp, method, path, body, secret):
    prehash = f"{timestamp}{method}{path}{body}"
    print(f"[bitget_api] sign prehash: {prehash}")
    hmac_key = secret.encode('utf-8')
    message = prehash.encode('utf-8')
    signature = hmac.new(hmac_key, message, digestmod=hashlib.sha256).digest()
    signature_b64 = base64.b64encode(signature).decode()
    print(f"[bitget_api] SIGNATURE: {signature_b64}")
    return signature_b64

def api_request(method, endpoint, params=None):
    api_key = get_env('BITGET_APIKEY')
    api_secret = get_env('BITGET_APISECRET')
    passphrase = get_env('BITGET_PASSPHRASE')

    timestamp = str(int(time.time() * 1000))
    method = method.upper()
    body = ''
    if method == "GET":
        if params:
            query_str = '&'.join(f"{k}={v}" for k, v in params.items())
            path = f"{endpoint}?{query_str}"
        else:
            path = endpoint
    else:
        path = endpoint
        body = params and json.dumps(params) or ''

    sign = sign_request(timestamp, method, endpoint, body, api_secret)

    headers = {
        "ACCESS-KEY": api_key,
        "ACCESS-SIGN": sign,
        "ACCESS-TIMESTAMP": timestamp,
        "ACCESS-PASSPHRASE": passphrase,
        "Content-Type": "application/json"
    }
    url = f"https://api.bitget.com{endpoint}"
    print(f"[bitget_api] Request: {method} {url}")
    print(f"[bitget_api] Headers: {headers}")

    try:
        if method == "GET":
            response = requests.get(url, headers=headers, timeout=10)
        else:
            response = requests.post(url, headers=headers, data=body, timeout=10)
    except Exception as e:
        print(f"[bitget_api] Network ERROR: {e}")
        return None

    print(f"[bitget_api] Raw Response: {response.status_code} {response.text}")
    try:
        return response.json()
    except:
        return {"error": response.text}

def test_bitget():
    """간단한 계좌 조회(정상시 'code': '00000' 반환)"""
    res = api_request("GET", "/api/v2/mix/account/accounts", params={"productType": "USDT-FUTURES"})
    print(f"[bitget_api] test_bitget result: {res}")
    return res
