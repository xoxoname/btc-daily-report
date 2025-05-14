# main.py
import os
import ccxt
import requests
from flask import Flask, jsonify
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
import pytz

app = Flask(__name__)
tz = pytz.timezone('Asia/Seoul')
latest_report = {}

def create_exchange():
    return ccxt.bitget({
        'apiKey': os.environ['BITGET_APIKEY'],
        'secret': os.environ['BITGET_SECRET'],
        'password': os.environ['BITGET_PASSPHRASE'],
        'enableRateLimit': True,
    })

def fetch_data():
    # 1) BTC 실시간 가격 (Coinbase spot)
    cb = requests.get('https://api.coinbase.com/v2/prices/spot?currency=USD').json()
    price = float(cb['data']['amount'])

    # 2) Bitget 순입금 조회
    exch = create_exchange()
    txs = exch.fetch_transactions()  # 모든 입출금 기록
    net_deposit = sum(float(t['amount']) if t['type']=='deposit' else -float(t['amount']) for t in txs if t['currency']=='USDT')

    # 3) Bitget 선물계좌 balance + PnL
    bal = exch.fetch_balance({'type': 'future'})
    info = bal['info']['data'][0]  # data 리스트 첫번째에 USDT 선물계좌 데이터
    unrealized = float(info.get('unrealizedProfit', 0))
    realized   = float(info.get('realizedProfit', 0))
    equity     = float(info.get('equity', bal['total'].get('USDT', 0)))

    # 4) 수익 & 수익률
    total_profit = realized + unrealized
    pct_return   = (total_profit / net_deposit * 100) if net_deposit else 0

    # 5) 호재/중립/악재 판단
    price_trend = '호재' if price > price * 0.995 else '악재' if price < price * 1.005 else '중립'

    return {
        'timestamp': datetime.now(tz).strftime('%Y-%m-%d %H:%M:%S'),
        'btc_price': price,
        'btc_trend': price_trend,
        'net_deposit': net_deposit,
        'equity': equity,
        'realized_pnl': realized,
        'unrealized_pnl': unrealized,
        'total_profit': total_profit,
        'percent_return': round(pct_return, 2),
        'encouragement': '지금까지 잘 해오셨습니다! 곧 더 큰 성과가 찾아올 거예요 🚀',
    }

def refresh_report():
    global latest_report
    try:
        latest_report = fetch_data()
    except Exception as e:
        latest_report = {'error': str(e)}

# 5분마다 리포트 자동 갱신
sched = BackgroundScheduler(timezone=tz)
sched.add_job(refresh_report, 'interval', minutes=5, next_run_time=datetime.now(tz))
sched.start()

@app.route('/')
def index():
    return 'Crypto Report Service is running!', 200

@app.route('/report')
def report():
    if not latest_report:
        refresh_report()
    return jsonify(latest_report)

if __name__ == '__main__':
    refresh_report()
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 10000)))
