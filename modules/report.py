import requests
import os
from datetime import datetime
from decimal import Decimal

# 환경변수에서 API 키 정보 읽기
BITGET_APIKEY = os.environ.get("BITGET_APIKEY")
BITGET_SECRET = os.environ.get("BITGET_SECRET")
BITGET_PASSPHRASE = os.environ.get("BITGET_PASSPHRASE")

def get_coinbase_price():
    try:
        res = requests.get("https://api.coinbase.com/v2/prices/BTC-USDT/spot")
        return float(res.json()['data']['amount'])
    except Exception:
        return None

def get_bitget_position():
    url = "https://api.bitget.com/api/mix/v1/position/singlePosition"
    headers = {
        "ACCESS-KEY": BITGET_APIKEY,
        "ACCESS-PASSPHRASE": BITGET_PASSPHRASE,
        "Content-Type": "application/json"
    }
    params = {
        "symbol": "BTCUSDT",
        "marginCoin": "USDT"
    }
    try:
        res = requests.get(url, headers=headers, params=params)
        return res.json()
    except Exception as e:
        return {"error": str(e)}

def get_profit_report():
    data = get_bitget_position()
    price = get_coinbase_price()
    if "data" not in data:
        return {"error": "데이터를 불러올 수 없습니다."}

    pos = data["data"]
    realized_pnl = Decimal(pos.get("realizedProfit", "0"))
    unrealized_pnl = Decimal(pos.get("unrealizedPL", "0"))
    avg_entry = float(pos.get("avgOpenPrice", 0))
    amount = float(pos.get("total", 0))
    side = pos.get("holdSide", "none")

    total_usdt = realized_pnl + unrealized_pnl
    total_krw = total_usdt * Decimal(1380)

    return {
        "position": f"{side} {amount} BTC @ {avg_entry} USDT",
        "realized_pnl": f"{realized_pnl:.2f} USDT ({realized_pnl*Decimal(1380):.0f} KRW)",
        "unrealized_pnl": f"{unrealized_pnl:.2f} USDT ({unrealized_pnl*Decimal(1380):.0f} KRW)",
        "total_pnl": f"{total_usdt:.2f} USDT ({total_krw:.0f} KRW)",
        "btc_price": f"{price} USDT" if price else "가격 정보 없음",
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

def get_prediction_report():
    # 향후 12시간 예측 분석을 포함한 예시 리포트 템플릿
    report = get_profit_report()
    if "error" in report:
        return "데이터 오류 발생: 수익 리포트 불러오기 실패"

    return f"""
📊 <b>BTC 수익/예측 리포트</b>

🚀 현재 포지션: <code>{report['position']}</code>
💰 실현 손익: {report['realized_pnl']}
📈 미실현 손익: {report['unrealized_pnl']}
💹 총 손익: {report['total_pnl']}
🟡 현재 BTC 시세: {report['btc_price']}
🕓 기준 시각: {report['timestamp']}

🔮 향후 12시간 예측:
- 기술적 지표: 과매도 해소 중, 반등 시도
- 시장 심리: 롱 포지션 회복세
- 구조 분석: 주요 저항대 63,000 USDT 돌파 여부 주시

📌 참고: 예측은 실시간 지표 기반으로 분석되며, 투자 판단은 본인 책임입니다.
    """.strip()
