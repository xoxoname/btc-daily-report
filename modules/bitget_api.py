import os
import time
import requests
import base64
import hmac
import json

# 환경변수에서 값 가져오기
BITGET_APIKEY = os.environ.get("BITGET_APIKEY")
BITGET_APISECRET = os.environ.get("BITGET_APISECRET")
BITGET_PASSPHRASE = os.environ.get("BITGET_PASSPHRASE")

# 디버깅용 실제 값 출력
print(f"BITGET_APIKEY = [{BITGET_APIKEY}]")
print(f"BITGET_APISECRET = [{BITGET_APISECRET}] (len={len(BITGET_APISECRET) if BITGET_APISECRET else 0})")
print(f"BITGET_PASSPHRASE = [{BITGET_PASSPHRASE}]")

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
    resp = requests.get(url, headers=headers)
    try:
        data = resp.json()
        print("get_usdt_futures_account 응답:", data)
        if "data" in data and isinstance(data["data"], dict):
            return data["data"]
        elif "msg" in data:
            return {"error": data["msg"]}
        else:
            return None
    except Exception as e:
        print("get_usdt_futures_account 예외:", e)
        return None

def get_positions(symbol="BTCUSDT"):
    path = "/api/v2/mix/position/single-position"
    url = f"https://api.bitget.com{path}?symbol={symbol}&productType=USDT-FUTURES"
    headers = get_headers("GET", path, "")
    resp = requests.get(url, headers=headers)
    try:
        data = resp.json()
        print("get_positions 응답:", data)
        if "data" in data and data["data"]:
            return data["data"]
        elif "msg" in data:
            return {"error": data["msg"]}
        else:
            return None
    except Exception as e:
        print("get_positions 예외:", e)
        return None

def get_profit_summary():
    # (샘플) 포지션과 계좌 정보를 활용해 리턴 포맷 생성
    acc = get_usdt_futures_account()
    pos = get_positions()
    if acc is None or pos is None:
        if isinstance(acc, dict) and "error" in acc:
            return {"error": acc["error"]}
        if isinstance(pos, dict) and "error" in pos:
            return {"error": pos["error"]}
        return {"error": "실시간 자산/포지션을 가져올 수 없습니다."}

    # (예시) 데이터에서 필요한 값만 추출해서 리턴 (실제 데이터 구조에 맞게 수정 필요)
    return {
        "종목": pos.get("symbol", "BTCUSDT"),
        "방향": pos.get("holdSide", "-"),
        "진입가": pos.get("openPriceAvg", "-"),
        "현재가": pos.get("last", "-"),
        "레버리지": pos.get("leverage", "-"),
        "청산가": pos.get("liquidationPrice", "-"),
        "청산까지 남은 거리": "-",
        "미실현 손익": pos.get("unrealizedPL", "-"),
        "실현 손익": acc.get("realizedPL", "-"),
        "진입 자산": acc.get("margin", "-"),
        "수익률": "-",
    }
