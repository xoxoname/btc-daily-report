import os
def get_position_info():
    # Bitget API 연동용 환경변수 사용 예시
    # api_key = os.environ["BITGET_APIKEY"]
    # api_secret = os.environ["BITGET_APISECRET"]
    # api_passphrase = os.environ["BITGET_PASSPHRASE"]
    return {
        "symbol": "BTCUSDT",
        "side": "롱",
        "entry_price": 65400,
        "current_price": 66210,
        "leverage": 10,
        "liq_price": 60930,
        "margin": 2000,
        "unrealized_pnl": 81.0,
        "realized_pnl": 24.3,
        "krw_usd": 1350
    }
