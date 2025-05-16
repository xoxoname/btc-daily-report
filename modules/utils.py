import requests

def fetch_coinbase_price():
    url = "https://api.coinbase.com/v2/prices/spot?currency=USD"
    response = requests.get(url)
    data = response.json()
    return float(data["data"]["amount"])

def fetch_bitget_position_data():
    # Bitget API를 사용하여 포지션 데이터를 조회하는 로직을 구현합니다.
    # 예시로 빈 딕셔너리를 반환합니다.
    return {}

def format_currency(value):
    return "${:,.2f}".format(value)
