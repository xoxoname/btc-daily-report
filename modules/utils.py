import requests
from modules.constants import BITGET_API_KEY, BITGET_API_SECRET, BITGET_PASSPHRASE

def fetch_btc_price():
    url = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd,krw"
    try:
        res = requests.get(url, timeout=10)
        data = res.json()
        return float(data["bitcoin"]["usd"]), float(data["bitcoin"]["krw"])
    except:
        return None, None

def fetch_bitget_data():
    # 예시용 가짜 데이터
    return {
        "realized_pnl": 152.33,
        "unrealized_pnl": 87.22,
        "entry_balance": 5000,
    }
