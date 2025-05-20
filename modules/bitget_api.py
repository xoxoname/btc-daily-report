import requests
import time
import hmac
import base64
import os

API_KEY = os.environ.get("BITGET_APIKEY")
API_SECRET = os.environ.get("BITGET_APISECRET")
PASSPHRASE = os.environ.get("BITGET_PASSPHRASE")

def make_headers(method, path, params=""):
    timestamp = str(int(time.time() * 1000))
    body = "" if method == "GET" else params
    prehash = timestamp + method + path + body
    sign = base64.b64encode(
        hmac.new(API_SECRET.encode('utf-8'), prehash.encode('utf-8'), digestmod='sha256').digest()
    ).decode()
    return {
        'ACCESS-KEY': API_KEY,
        'ACCESS-SIGN': sign,
        'ACCESS-TIMESTAMP': timestamp,
        'ACCESS-PASSPHRASE': PASSPHRASE,
        'Content-Type': 'application/json'
    }

def get_profit_summary():
    # USDT-FUTURES 잔고 조회 예시
    url = "https://api.bitget.com/api/v2/mix/account/accounts?productType=USDT-FUTURES"
    headers = make_headers("GET", "/api/v2/mix/account/accounts", "productType=USDT-FUTURES")
    res = requests.get(url, headers=headers)
    try:
        data = res.json()
        # 여기에 실제 내 자산구조 분석(positions, balance 등) 맞게 가공해서 리포트 반환
        # 예시만 아래처럼
        # {"data":{"totalEquity":"1234.56","usdtEquity":"1234.56", ...}}
        if "data" in data and isinstance(data["data"], dict):
            return {
                "종목": "BTCUSDT",
                "방향": "롱",
                "진입가": "66400",
                "현재가": "66600",
                "레버리지": "10x",
                "청산가": "61500",
                "청산까지 남은 거리": "-7.8%",
                "미실현 손익": "+$100.0 (13.5만원)",
                "실현 손익": "+$30.0 (4.0만원)",
                "진입 자산": "$2,000",
                "수익률": "+6.5%",
            }
        else:
            return None
    except Exception as e:
        return None
