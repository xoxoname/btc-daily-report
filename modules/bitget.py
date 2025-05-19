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
    def _headers(method, path, params=""):
        timestamp = str(int(time.time() * 1000))
        if method == "GET":
            body = ""
        else:
            body = json.dumps(params) if params else ""
        pre_sign = timestamp + method + path + body
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
        params = {
            "symbol": "BTCUSDT_UMCBL",
            "marginCoin": "USDT",
        }
        url = BitgetClient.BASE_URL + path + f"?symbol={params['symbol']}&marginCoin={params['marginCoin']}"
        headers = BitgetClient._headers(method, path)
        resp = requests.get(url, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") != "00000":
            return []
        result = []
        for pos in data["data"]:
            if float(pos["holdVol"]) > 0:
                result.append({
                    "symbol": pos["symbol"],
                    "holdSide": pos["holdSide"],  # "long" or "short"
                    "avgOpenPrice": float(pos["avgOpenPrice"]),
                    "margin": float(pos["margin"]),
                    "upl": float(pos["unrealizedPL"]),
                    "realisedPnl": float(pos["achievedProfits"]),
                    "leverage": int(pos["leverage"]),
                    "liquidationPrice": float(pos["liquidationPrice"]),
                })
        return result

    @staticmethod
    def get_wallet():
        method = "GET"
        path = "/api/v2/mix/account/account"
        params = {
            "symbol": "BTCUSDT_UMCBL",
            "marginCoin": "USDT",
        }
        url = BitgetClient.BASE_URL + path + f"?symbol={params['symbol']}&marginCoin={params['marginCoin']}"
        headers = BitgetClient._headers(method, path)
        resp = requests.get(url, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") != "00000":
            return {"equity": 0}
        return {"equity": float(data["data"]["marginEquity"])}

