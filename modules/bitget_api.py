import os
import time
import requests
import base64
import hmac
import json

API_KEY = os.getenv("BITGET_APIKEY")
API_SECRET = os.getenv("BITGET_APISECRET")
API_PASSPHRASE = os.getenv("BITGET_PASSPHRASE")

def bitget_signature(timestamp, method, path, body):
    prehash = f"{timestamp}{method}{path}{body}"
    sign = hmac.new(API_SECRET.encode(), prehash.encode(), digestmod='sha256').digest()
    return base64.b64encode(sign).decode()

def get_headers(method, path, body=""):
    timestamp = str(int(time.time() * 1000))
    sign = bitget_signature(timestamp, method, path, body)
    return {
        "ACCESS-KEY": API_KEY,
        "ACCESS-SIGN": sign,
        "ACCESS-TIMESTAMP": timestamp,
        "ACCESS-PASSPHRASE": API_PASSPHRASE,
        "Content-Type": "application/json"
    }

def get_profit_summary():
    # 기본값 (오류 시 None 반환)
    result = {"error": None}
    try:
        # 계좌 정보 조회
        path1 = "/api/v2/mix/account/accounts"
        url1 = f"https://api.bitget.com{path1}?productType=USDT-FUTURES"
        headers1 = get_headers("GET", path1, "")
        resp1 = requests.get(url1, headers=headers1, timeout=10)
        try:
            data1 = resp1.json()
        except Exception as e:
            result["error"] = f"API 응답 JSON 파싱 실패: {e}"
            return result
        if "code" in data1 and str(data1["code"]) != "00000":
            result["error"] = f"Bitget API 오류: {data1.get('msg', 'Unknown error')} (code: {data1['code']})"
            return result
        account = data1.get("data", {}).get("totalEquity", None)
        if not account:
            result["error"] = "Bitget 계좌 정보 없음 또는 데이터 구조 변경"
            return result

        # 포지션 정보 조회 (BTCUSDT)
        path2 = "/api/v2/mix/position/single-position"
        url2 = f"https://api.bitget.com{path2}?symbol=BTCUSDT&productType=USDT-FUTURES"
        headers2 = get_headers("GET", path2, "")
        resp2 = requests.get(url2, headers=headers2, timeout=10)
        try:
            data2 = resp2.json()
        except Exception as e:
            result["error"] = f"API 응답 JSON 파싱 실패(포지션): {e}"
            return result
        if "code" in data2 and str(data2["code"]) != "00000":
            result["error"] = f"Bitget API 오류(포지션): {data2.get('msg', 'Unknown error')} (code: {data2['code']})"
            return result
        positions = data2.get("data", None)
        if not positions:
            result["error"] = "Bitget 포지션 정보 없음(미보유 중이거나 API 구조 변경)"
            return result

        # 예시: 실제 데이터 키는 Bitget 문서 확인 필요
        # (아래 키 값은 반드시 실제 응답에 맞게 수정!)
        profit_summary = {
            "종목": positions.get("symbol", "BTCUSDT"),
            "방향": positions.get("holdSide", "-"),
            "진입가": positions.get("openAvgPrice", "-"),
            "현재가": positions.get("last", "-"),
            "레버리지": positions.get("leverage", "-"),
            "청산가": positions.get("liqPx", "-"),
            "청산까지 남은 거리": "-",
            "미실현 손익": positions.get("unRealizedPL", "-"),
            "실현 손익": positions.get("realizedPL", "-"),
            "진입 자산": account,
            "수익률": "-"
        }
        return profit_summary

    except requests.exceptions.Timeout:
        result["error"] = "Bitget API 요청 타임아웃"
    except requests.exceptions.RequestException as e:
        result["error"] = f"Bitget 네트워크 오류: {e}"
    except Exception as e:
        result["error"] = f"알 수 없는 오류: {e}"
    return result
