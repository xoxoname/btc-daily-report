import os
import time
import requests
import base64
import hmac
import json

BITGET_APIKEY = os.environ.get("BITGET_APIKEY")
BITGET_APISECRET = os.environ.get("BITGET_APISECRET")
BITGET_PASSPHRASE = os.environ.get("BITGET_PASSPHRASE")

# 1. 인증정보 확인
print(f"BITGET_APIKEY = [{BITGET_APIKEY}]")
print(f"BITGET_APISECRET = [{BITGET_APISECRET}] (len={len(BITGET_APISECRET) if BITGET_APISECRET else 0})")
print(f"BITGET_PASSPHRASE = [{BITGET_PASSPHRASE}]")

def bitget_signature(timestamp, method, path, body):
    prehash = f"{timestamp}{method}{path}{body}"
    # print("prehash:", prehash)
    sign = hmac.new(BITGET_APISECRET.encode(), prehash.encode(), digestmod='sha256').digest()
    signature = base64.b64encode(sign).decode()
    print(f"Signature: {signature}")
    return signature

def get_headers(method, path, body=""):
    timestamp = str(int(time.time() * 1000))
    sign = bitget_signature(timestamp, method, path, body)
    headers = {
        "ACCESS-KEY": BITGET_APIKEY,
        "ACCESS-SIGN": sign,
        "ACCESS-TIMESTAMP": timestamp,
        "ACCESS-PASSPHRASE": BITGET_PASSPHRASE,
        "Content-Type": "application/json"
    }
    print("Headers:", headers)
    return headers

def get_usdt_futures_account():
    path = "/api/v2/mix/account/accounts"
    url = f"https://api.bitget.com{path}?productType=USDT-FUTURES"
    headers = get_headers("GET", path, "")
    print("Request URL:", url)
    try:
        resp = requests.get(url, headers=headers)
        print("Raw Response:", resp.status_code, resp.text)
        data = resp.json()
        if "data" in data and isinstance(data["data"], dict):
            return data["data"]
        elif "msg" in data:
            return {"error": data["msg"], "raw": data}
        else:
            return {"error": "unknown_error", "raw": data}
    except Exception as e:
        print("get_usdt_futures_account Exception:", e)
        return {"error": str(e)}

def get_positions(symbol="BTCUSDT"):
    path = "/api/v2/mix/position/single-position"
    url = f"https://api.bitget.com{path}?symbol={symbol}&productType=USDT-FUTURES"
    headers = get_headers("GET", path, "")
    print("Request URL:", url)
    try:
        resp = requests.get(url, headers=headers)
        print("Raw Response:", resp.status_code, resp.text)
        data = resp.json()
        if "data" in data and data["data"]:
            return data["data"]
        elif "msg" in data:
            return {"error": data["msg"], "raw": data}
        else:
            return {"error": "unknown_error", "raw": data}
    except Exception as e:
        print("get_positions Exception:", e)
        return {"error": str(e)}

def get_profit_summary():
    acc = get_usdt_futures_account()
    pos = get_positions()
    # 오류가 있으면 명확하게 반환
    if isinstance(acc, dict) and "error" in acc:
        print("[Bitget 계정 에러]", acc["error"], acc.get("raw"))
        return {"error": acc["error"]}
    if isinstance(pos, dict) and "error" in pos:
        print("[Bitget 포지션 에러]", pos["error"], pos.get("raw"))
        return {"error": pos["error"]}
    if acc is None or pos is None:
        print("[Bitget 데이터 없음]")
        return {"error": "실시간 자산/포지션을 가져올 수 없습니다."}
    # 정상일 때만 실제 값 리턴(포맷 예시)
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
