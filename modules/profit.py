import requests
import time
import hmac
import hashlib
import base64
from modules.constants import BITGET_APIKEY, BITGET_APISECRET, BITGET_PASSPHRASE

def get_bitget_signature(timestamp, method, request_path, body=""):
    pre_hash = f"{timestamp}{method}{request_path}{body}"
    secret_bytes = BITGET_APISECRET.encode("utf-8")
    return base64.b64encode(hmac.new(secret_bytes, pre_hash.encode("utf-8"), hashlib.sha256).digest()).decode()

def generate_profit():
    try:
        timestamp = str(int(time.time() * 1000))
        method = "GET"
        request_path = "/api/mix/v1/position/singlePosition?symbol=BTCUSDT&marginCoin=USDT"
        url = f"https://api.bitget.com{request_path}"
        signature = get_bitget_signature(timestamp, method, request_path)
        headers = {
            "ACCESS-KEY": BITGET_APIKEY,
            "ACCESS-SIGN": signature,
            "ACCESS-TIMESTAMP": timestamp,
            "ACCESS-PASSPHRASE": BITGET_PASSPHRASE,
        }
        res = requests.get(url, headers=headers)
        data = res.json().get("data", {})

        entry_price = float(data.get("openPrice", 0))
        mark_price = float(data.get("marketPrice", 0))
        pnl = float(data.get("unrealizedPL", 0))
        leverage = float(data.get("leverage", 1))
        liquidation_price = float(data.get("liquidationPrice", 0))
        margin = float(data.get("margin", 1))
        profit_rate = (pnl / margin * 100) if margin else 0

        return f"""
💰 현재 수익 현황 요약
━━━━━━━━━━━━━━━━━━━
📌 포지션 정보
- 종목: BTCUSDT
- 방향: 롱
- 진입가: ${entry_price}
- 현재가: ${mark_price}
- 레버리지: {leverage}x
- 청산가: ${liquidation_price}

━━━━━━━━━━━━━━━━━━━
💸 손익 정보
- 미실현 손익: ${pnl:.2f}
- 진입 자산: ${margin}
- 수익률: {profit_rate:.2f}%
━━━━━━━━━━━━━━━━━━━
🧠 멘탈 코멘트
지금 수익이 적어도 방향이 맞다면 기다리는 것도 전략입니다.
"""
    except Exception as e:
        return f"⚠️ Bitget API 실패: {str(e)}"
