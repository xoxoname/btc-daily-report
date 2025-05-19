import requests

def get_coinbase_btc_price():
    try:
        resp = requests.get("https://api.coinbase.com/v2/prices/BTC-USD/spot")
        if resp.status_code == 200:
            return float(resp.json()["data"]["amount"])
        return None
    except Exception:
        return None
