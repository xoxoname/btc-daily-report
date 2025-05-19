import os
import requests

def get_positions():
    # 실제 Bitget API 연동 예시(미니멀)
    # 실제로는 signature 등 인증과정 필요, 아래는 예시/mockup
    return {
        "symbol": "BTCUSDT",
        "side": "롱",
        "openPrice": 67000,
        "currentPrice": 68000,
        "leverage": 10,
        "liquidationPrice": 60000,
        "unrealizedPnl": 200,
        "margin": 2000,
    }

def get_profit_history():
    # 실 구현 시 Bitget API 실현손익 등 받아오기
    return {
        "realizedPnl": 340,
        "todayPnl": 340
    }
