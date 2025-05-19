import os
def get_position_info():
    # Bitget 연동 시 아래 환경변수 사용:
    # os.environ["BITGET_APIKEY"]
    # os.environ["BITGET_APISECRET"]
    # os.environ["BITGET_PASSPHRASE"]
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
