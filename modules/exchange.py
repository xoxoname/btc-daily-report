import os
import requests

def get_position_info():
    # Bitget API 키 환경변수
    API_KEY = os.environ.get("BITGET_APIKEY")
    API_SECRET = os.environ.get("BITGET_APISECRET")
    API_PASSPHRASE = os.environ.get("BITGET_PASSPHRASE")
    # 실시간 자산/포지션 가져오기 (샘플: 실제 연동 필요)
    # 참고: Bitget REST API v2 - /api/mix/v1/position/singlePosition
    # 아래는 예시, 실제 production에서는 제대로 된 인증 필요!
    # 문서: https://www.bitget.com/api-doc/contract/positions/Get-Current-Position
    try:
        url = "https://api.bitget.com/api/mix/v1/position/singlePosition"
        params = {
            "symbol": "BTCUSDT",
            "marginCoin": "USDT",
            "productType": "umcbl"
        }
        headers = {
            "ACCESS-KEY": API_KEY,
            "ACCESS-SIGN": "",
            "ACCESS-TIMESTAMP": "",
            "ACCESS-PASSPHRASE": API_PASSPHRASE,
            "Content-Type": "application/json"
        }
        # 실제 Bitget 인증과정은 별도 util로 분리 필요, 아래는 샘플/임시
        resp = requests.get(url, params=params, headers=headers, timeout=5)
        data = resp.json()
        pos = data.get('data', {})
        # 여기서 실제 데이터 파싱
        return {
            "symbol": pos.get('symbol', 'BTCUSDT'),
            "side": "롱" if float(pos.get('holdSide', 1)) > 0 else "숏",
            "entry_price": float(pos.get('openPrice', 65400)),
            "current_price": float(pos.get('marketPrice', 66210)),
            "leverage": float(pos.get('leverage', 10)),
            "liq_price": float(pos.get('liquidationPrice', 60930)),
            "margin": float(pos.get('margin', 2000)),
            "unrealized_pnl": float(pos.get('unrealizedPL', 81)),
            "realized_pnl": float(pos.get('realizedPL', 24)),
            "krw_usd": 1350
        }
    except Exception as e:
        # 오류시 임시 더미값 반환
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
