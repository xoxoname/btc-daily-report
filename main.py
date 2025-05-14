import os
import time
import requests
import ccxt
from flask import Flask, jsonify
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
latest_report = {"message": "리포트 초기화 중..."}

def create_exchange():
    api_key = os.getenv("BITGET_API_KEY")
    secret = os.getenv("BITGET_SECRET")
    password = os.getenv("BITGET_PASSPHRASE")
    if not all([api_key, secret, password]):
        raise ValueError("Bitget API 키 누락됨 (환경변수 확인 필요)")
    return ccxt.bitget({
        'apiKey': api_key,
        'secret': secret,
        'password': password,
        'enableRateLimit': True,
    })

def get_coinbase_price():
    try:
        r = requests.get("https://api.coinbase.com/v2/prices/BTC-USD/spot")
        return float(r.json()["data"]["amount"])
    except:
        return None

def gpt_insight_analysis(price):
    summary = {
        "macro": "금일 주요 발표 없음. CPI 발표는 이번 주 목요일 예정.",
        "technical": "MACD 하락 전환, RSI 중립 (52), 볼린저밴드 상단에서 저항받는 중",
        "sentiment": "Fear & Greed Index: 54 (중립), 트위터 여론은 관망 흐름",
        "prediction": {
            "12h_up_probability": 35,
            "12h_down_probability": 65,
            "reason": "DXY 반등 + MACD 하락 전환 → 단기 하락 우세"
        }
    }
    return summary

def fetch_data():
    try:
        exch = create_exchange()
    except ValueError as ve:
        return {"error": str(ve)}

    try:
        balance = exch.fetch_balance({'type': 'swap'})
        equity = float(balance['total'].get('USDT', 0))

        positions = exch.fetch_positions()
        open_positions = []
        unrealized_total = 0.0

        for pos in positions:
            if float(pos['contracts']) > 0:
                pnl = float(pos['unrealizedPnl'])
                unrealized_total += pnl
                open_positions.append({
                    "symbol": pos['symbol'],
                    "side": pos['side'],
                    "entry": pos['entryPrice'],
                    "amount": pos['contracts'],
                    "unrealized": round(pnl, 2)
                })

        # 수익률 계산
        initial_equity = float(os.getenv("INITIAL_EQUITY", "1000"))
        change_pct = round((equity - initial_equity) / initial_equity * 100, 2)

        # 가격 정보
        spot_price = get_coinbase_price()

        # GPT 매동 예측 분석
        gpt = gpt_insight_analysis(spot_price)

        return {
            "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "coinbase_price": spot_price,
            "gpt_forecast": gpt,
            "equity": round(equity, 2),
            "change_pct": change_pct,
            "open_positions": open_positions,
            "unrealized_pnl": round(unrealized_total, 2),
            "message": "리포트가 정상적으로 생성되었습니다."
        }

    except Exception as e:
        return {"error": str(e)}

def update_report():
    global latest_report
    latest_report = fetch_data()

@app.route("/")
def home():
    return "BTC 정규 리포트 Web Service입니다."

@app.route("/report")
def report():
    return jsonify(fetch_data())

# 백그라운드 5분마다 실행
scheduler = BackgroundScheduler()
scheduler.add_job(func=update_report, trigger="interval", minutes=5)
scheduler.start()

# 초기 보고서 한 번 실행
if __name__ == "__main__":
    update_report()
    app.run(host='0.0.0.0', port=10000)
