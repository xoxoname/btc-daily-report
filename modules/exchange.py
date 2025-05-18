import os
import time
import hmac
import hashlib
import base64
import json
import requests
from urllib3.util.ssl_ import create_urllib3_context
from requests.adapters import HTTPAdapter

class TLSAdapter(HTTPAdapter):
    def init_poolmanager(self, *args, **kwargs):
        context = create_urllib3_context()
        kwargs['ssl_context'] = context
        return super().init_poolmanager(*args, **kwargs)

class BitgetAPI:
    def __init__(self):
        self.api_key = os.getenv("BITGET_APIKEY")
        self.secret = os.getenv("BITGET_APISECRET")
        self.passphrase = os.getenv("BITGET_PASSPHRASE")
        self.base_url = "https://api.bitget.com"
        self.session = requests.Session()
        self.session.mount("https://", TLSAdapter())

    def _timestamp(self):
        return str(int(time.time() * 1000))

    def _sign(self, method, path, query_string=""):
        timestamp = self._timestamp()
        message = f"{timestamp}{method.upper()}{path}{query_string}"
        print("▼▼ 서명 검증 메시지 ▼▼")
        print(message)
        signature = base64.b64encode(hmac.new(
            self.secret.encode(), message.encode(), hashlib.sha256
        ).digest()).decode()
        return timestamp, signature

    def _headers(self, method, path, query_string=""):
        timestamp, signature = self._sign(method, path, query_string)
        return {
            "ACCESS-KEY": self.api_key,
            "ACCESS-SIGN": signature,
            "ACCESS-TIMESTAMP": timestamp,
            "ACCESS-PASSPHRASE": self.passphrase,
            "Content-Type": "application/json"
        }

    def get_account_info(self):
        try:
            path = "/api/mix/v1/account/accounts"
            query = "?productType=USDT-FUTURES"
            url = f"{self.base_url}{path}{query}"
            headers = self._headers("GET", path, query)
            res = self.session.get(url, headers=headers, timeout=10)
            return res.json()
        except Exception as e:
            print(f"🚨 계정 정보 오류: {e}")
            return {}

    def get_position_info(self):
        try:
            path = "/api/mix/v1/position/singlePosition"
            query = "?symbol=BTCUSDT_UMCBL&marginCoin=USDT"
            url = f"{self.base_url}{path}{query}"
            headers = self._headers("GET", path, query)
            res = self.session.get(url, headers=headers, timeout=10)
            return res.json()
        except Exception as e:
            print(f"🚨 포지션 정보 오류: {e}")
            return {}