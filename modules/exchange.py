import requests

class BitgetAPI:
    def __init__(self, api_key, secret, passphrase):
        self.api_key = api_key
        self.secret = secret
        self.passphrase = passphrase

    def get_market_data(self):
        url = 'https://api.bitget.com/api/mix/v1/market/ticker?symbol=BTCUSDT_UMCBL'
        resp = requests.get(url)
        data = resp.json()['data']
        return {
            'price': float(data['last']),
            'volume': float(data['baseVolume']),
            'change': float(data['usdtVolume'])
        }

    def get_funding_rate(self):
        url = 'https://api.bitget.com/api/mix/v1/market/funding-rate?symbol=BTCUSDT_UMCBL'
        resp = requests.get(url)
        return float(resp.json()['data']['fundingRate'])

    def get_open_interest(self):
        url = 'https://api.bitget.com/api/mix/v1/market/open-interest?symbol=BTCUSDT_UMCBL'
        resp = requests.get(url)
        data = resp.json()['data']
        return {
            'openInterest': float(data['openInterest']),
            'change': float(data['openInterestChange']) if 'openInterestChange' in data else 0.0
        }
