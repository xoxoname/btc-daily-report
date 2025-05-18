import os, requests, hmac, hashlib, base64, time, json
from modules.tls_adapter import session

class BitgetAPI:
    def __init__(self):
        self.api_key = os.getenv("BITGET_APIKEY")
        self.secret = os.getenv("BITGET_APISECRET")
        self.passphrase = os.getenv("BITGET_PASSPHRASE")

    def _sign(self, method, path, params=""):
        timestamp = str(int(time.time() * 1000))
        message = f"{timestamp}{method.upper()}{path}{params}"
        signature = base64.b64encode(
            hmac.new(self.secret.encode(), message.encode(), hashlib.sha256).digest()
        ).decode()
        return {
            "ACCESS-KEY": self.api_key,
            "ACCESS-SIGN": signature,
            "ACCESS-TIMESTAMP": timestamp,
            "ACCESS-PASSPHRASE": self.passphrase,
        }

    def get_account_info(self):
        path = "/api/mix/v1/account/accounts"
        params = "?productType=USDT-FUTURES"
        url = f"https://api.bitget.com{path}{params}"
        headers = self._sign("GET", path, params)
        r = session.get(url, headers=headers, timeout=10)
        return r.json()

    def get_position_info(self):
        path = "/api/mix/v1/position/singlePosition"
        params = "?symbol=BTCUSDT_UMCBL&marginCoin=USDT"
        url = f"https://api.bitget.com{path}{params}"
        headers = self._sign("GET", path, params)
        r = session.get(url, headers=headers, timeout=10)
        return r.json()
