import requests

def fetch_coinbase_price():
    try:
        url = "https://api.coinbase.com/v2/prices/spot?currency=USD"
        response = requests.get(url)
        response.raise_for_status()
        return float(response.json()["data"]["amount"])
    except Exception:
        return None

def fetch_bitget_position_data():
    try:
        url = "https://btc-daily-report.onrender.com/report"
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        return data
    except Exception:
        return None

def format_currency(value, unit="USD"):
    try:
        formatted = f"${value:,.2f}" if unit == "USD" else f"{value:,.0f}원"
        return formatted
    except Exception:
        return value
