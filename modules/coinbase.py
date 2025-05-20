import requests

def get_coinbase_price(symbol="BTC-USD"):
    url = f"https://api.coinbase.com/v2/prices/{symbol}/spot"
    r = requests.get(url)
    r.raise_for_status()
    return float(r.json()["data"]["amount"])
