import os
import requests
import time
import hashlib
import hmac
import base64
import json

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
    def get_btcusdt_ticker():
        url = f"{BitgetClient.BASE_URL}/api/mix/v1/market/ticker?symbol=BTCUSDT_UMCBL"
        resp = requests.get(url)
        resp.raise_for_status()
        return float(resp.json()["data"]["last"])

    @staticmethod
    def get_positions():
        method = "GET"
        path = "/api/mix/v1/position/singlePosition"
        query = "symbol=BTCUSDT_UMCBL&marginCoin=USDT"
        url = BitgetClient.BASE_URL + path + "?" + query
        headers = BitgetClient._headers(method, path, query)
        resp = requests.get(url, headers=headers)
        # [핵심] 오류 발생 시 빈 리스트 반환
        try:
            resp.raise_for_status()
            data = resp.json()
            if data.get("code") != "00000":
                return []
            pos = data.get("data")
            if not pos or float(pos.get("holdVol", 0)) == 0:
                return []
            return [{
                "symbol": pos["symbol"],
                "holdSide": pos["holdSide"],  # "long" or "short"
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

    @staticmethod
    def get_wallet():
        method = "GET"
        path = "/api/v2/mix/account/account"
        query = "symbol=BTCUSDT_UMCBL&marginCoin=USDT"
        url = BitgetClient.BASE_URL + path + "?" + query
        headers = BitgetClient._headers(method, path, query)
        try:
            resp = requests.get(url, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            if data.get("code") != "00000":
                return {"equity": 0}
            return {"equity": float(data["data"]["marginEquity"])}
        except Exception as e:
            print("Bitget Wallet API 오류:", e)
            return {"equity": 0}
