import os
import requests

def get_bitget_data():
    return {
        "positions": [{
            "symbol": "BTCUSDT",
            "entry_price": 10200,
            "current_price": 10050,
            "pnl_usd": -150,
            "pnl_krw": -205000
        }],
        "return_rate": -7.1,
        "realized": -20,
        "deposit": 2100,
        "now_asset": 1930,
        "total_pnl": 170,
        "total_krw": 232000,
        "weekly_return": 4.2
    }