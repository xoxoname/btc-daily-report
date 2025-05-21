import os
import time
import requests
import base64
import hmac

BITGET_APIKEY = os.environ.get("BITGET_APIKEY")
BITGET_APISECRET = os.environ.get("BITGET_APISECRET")
BITGET_PASSPHRASE = os.environ.get("BITGET_PASSPHRASE")

# 환경 변수 체크(디버깅용, 실제 배포시 print 삭제해도 됨)
print(f"API_KEY = [{BITGET_APIKEY}]")
print(f"API_SECRET = [{BITGET_APISECRET}] ({len(BITGET_APISECRET)})")
print(f"API_PASSPHRASE = [{BITGET_PASSPHRASE}]")

def bitget_signature(timestamp, method, path, body):
    prehash = f"{timestamp}{method}{path}{body}"
    sign = hmac.new(BITGET_APISECRET.encode(), prehash.encode(), digestmod='sha256').digest()
    return base64.b64encode(sign).decode()

def get_headers(method, path, body=""):
    timestamp = str(int(time.time() * 1000))
    sign = bitget_signature(timestamp, method, path, body)
    return {
        "ACCESS-KEY": BITGET_APIKEY,
        "ACCESS-SIGN": sign,
        "ACCESS-TIMESTAMP": timestamp,
        "ACCESS-PASSPHRASE": BITGET_PASSPHRASE,
        "Content-Type": "application/json"
    }

def get_usdt_futures_account():
    path = "/api/v2/mix/account/accounts"
    url = f"https://api.bitget.com{path}?productType=USDT-FUTURES"
    headers = get_headers("GET", path, "")
    try:
        resp = requests.get(url, headers=headers, timeout=5)
        data = resp.json()
        # 비트겟 오류 메시지 직접 반환
        if "code" in data and data["code"] != "00000":
            return {"error": f"{data.get('msg') or data.get('message', '')}"}
        if "data" in data and isinstance(data["data"], dict):
            return data["data"]
        else:
            return {"error": "No account data"}
    except Exception as e:
        return {"error": str(e)}

def get_profit_summary():
    # 실제 데이터 연동 안된 상태 예시
    # 아래 코드는 비트겟 정상 응답/에러 모두 캐치 가능
    account = get_usdt_futures_account()
    if "error" in account:
        return {"error": account["error"]}
    # 아래는 임시 값
    return {
        "종목": "BTCUSDT",
        "방향": "LONG",
        "진입가": "68200.5",
        "현재가": "68510.2",
        "레버리지": "20x",
        "청산가": "61000.0",
        "청산까지 남은 거리": "7.5%",
        "미실현 손익": "+190 USDT",
        "실현 손익": "+500 USDT",
        "진입 자산": "2500 USDT",
        "수익률": "+28.0%"
    }
