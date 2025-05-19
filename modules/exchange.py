def get_position_info():
    # 실서비스 연결 시 Bitget API 사용. 여기선 예시값 반환.
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
        "krw_usd": 1350  # 환율 예시
    }
