import os
import requests
import time
import hashlib
import hmac
import base64

class BitgetClient:
    BASE_URL = "https://api.bitget.com"
    APIKEY = os.environ.get("BITGET_APIKEY")
    APISECRET = os.environ.get("BITGET_APISECRET")
    PASSPHRASE = os.environ.get("BITGET_PASSPHRASE")

    @staticmethod
    def _headers(method, path, query=None, body=""):
        timestamp = str(int(time.time() * 1000))
        query_str = f"?{query}" if query else ""
        pre_sign = f"{timestamp}{method}{path}{query_str}{body}"
        sign = base64.b64encode(
            hmac.new(BitgetClient.APISECRET.encode(), pre_sign.encode(), hashlib.sha256).digest()
        ).decode()
        return {
            "ACCESS-KEY": BitgetClient.APIKEY,
            "ACCESS-SIGN": sign,
            "ACCESS-TIMESTAMP": timestamp,
            "ACCESS-PASSPHRASE": BitgetClient.PASSPHRASE,
            "Content-Type": "application/json",
        }

    @staticmethod
    def get_positions():
        method = "GET"
        path = "/api/mix/v1/position/singlePosition"
        query = "symbol=BTCUSDT_UMCBL&marginCoin=USDT"
        url = BitgetClient.BASE_URL + path + "?" + query
        headers = BitgetClient._headers(method, path, query)
        resp = requests.get(url, headers=headers)
        # 디버깅 정보 추가
        print("Bitget 요청:", url)
        print("헤더:", headers)
        print("응답코드:", resp.status_code)
        print("응답내용:", resp.text)
        try:
            resp.raise_for_status()
            data = resp.json()
            if data.get("code") != "00000":
                print("Bitget API 내부 응답코드:", data.get("code"))
                return []
            pos = data.get("data")
            if not pos or float(pos.get("holdVol", 0)) == 0:
                return []
            return [{
                "symbol": pos["symbol"],
                "holdSide": pos["holdSide"],
                "avgOpenPrice": float(pos["avgOpenPrice"]),
                "margin": float(pos["margin"]),
                "upl": float(pos["unrealizedPL"]),
                "realisedPnl": float(pos["achievedProfits"]),
                "leverage": int(pos["leverage"]),
                "liquidationPrice": float(pos["liquidationPrice"]),
            }]
        except Exception as e:
            print("Bitget Position API 오류:", e)
            return []
