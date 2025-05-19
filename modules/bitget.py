import os
import requests

class BitgetClient:
    BASE_URL = "https://api.bitget.com"
    APIKEY = os.environ.get("BITGET_APIKEY")
    APISECRET = os.environ.get("BITGET_APISECRET")
    PASSPHRASE = os.environ.get("BITGET_PASSPHRASE")

    @staticmethod
    def get_btcusdt_ticker():
        url = f"{BitgetClient.BASE_URL}/api/mix/v1/market/ticker?symbol=BTCUSDT_UMCBL"
        r = requests.get(url)
        r.raise_for_status()
        data = r.json()
        price = float(data["data"]["last"])
        return price

    @staticmethod
    def get_positions():
        # 실제 API 연동 구현 필요(아래는 데모)
        # "BTCUSDT_UMCBL" 기준으로만 샘플 구조
        # API Key Header 등 추가 필요
        # 여기선 구조 데모로 반환, 실제 연동은 공식문서 참고
        return [{
            "symbol": "BTCUSDT_UMCBL",
            "holdSide": "long",
            "avgOpenPrice": 67000,
            "margin": 2000,
            "upl": 200,  # 미실현 손익
            "realisedPnl": 340,  # 실현 손익
            "leverage": 10,
            "liquidationPrice": 60000,
        }]

    @staticmethod
    def get_wallet():
        # 실제 API 연동 구현 필요
        return {"equity": 2340}

