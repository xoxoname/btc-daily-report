import os
import time
import requests
import hmac
import hashlib
import base64

# 환경변수에서 키 읽기 (Render 설정 그대로)
BITGET_APIKEY = os.environ.get('BITGET_APIKEY')
BITGET_APISECRET = os.environ.get('BITGET_APISECRET')
BITGET_PASSPHRASE = os.environ.get('BITGET_PASSPHRASE')

def get_bitget_signature(timestamp, method, request_path, body, secret):
    # Bitget 공식 문서 기준 서명 방식
    prehash = f"{timestamp}{method.upper()}{request_path}{body or ''}"
    signature = base64.b64encode(
        hmac.new(
            secret.encode('utf-8'),
            prehash.encode('utf-8'),
            digestmod=hashlib.sha256
        ).digest()
    )
    return signature.decode()

def get_bitget_headers(method, request_path, body=""):
    timestamp = str(int(time.time() * 1000))
    signature = get_bitget_signature(timestamp, method, request_path, body, BITGET_APISECRET)
    headers = {
        "ACCESS-KEY": BITGET_APIKEY,
        "ACCESS-SIGN": signature,
        "ACCESS-TIMESTAMP": timestamp,
        "ACCESS-PASSPHRASE": BITGET_PASSPHRASE,
        "Content-Type": "application/json"
    }
    return headers

def get_bitget_accounts():
    method = "GET"
    request_path = "/api/v2/mix/account/accounts?productType=USDT-FUTURES"
    url = "https://api.bitget.com" + request_path
    body = ""  # GET 요청이므로 body 없음

    headers = get_bitget_headers(method, request_path, body)
    response = requests.get(url, headers=headers)
    return response.json()

if __name__ == "__main__":
    # 환경변수 정상 로딩 확인
    print("APIKEY:", BITGET_APIKEY)
    print("APISECRET:", BITGET_APISECRET)
    print("PASSPHRASE:", BITGET_PASSPHRASE)
    # 실제 Bitget 연동 테스트
    result = get_bitget_accounts()
    print("Bitget API 응답:", result)
