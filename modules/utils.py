import requests
import datetime

def get_btc_price():
    url = "https://api.coinbase.com/v2/prices/spot?currency=USD"
    response = requests.get(url)
    return float(response.json()["data"]["amount"])

def format_datetime(dt):
    return dt.strftime("%Y-%m-%d %H:%M (KST)")
